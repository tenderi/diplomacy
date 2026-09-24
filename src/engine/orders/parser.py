"""One grammar for parsing and formatting Diplomacy orders.

``parse_order`` turns a free-form order string (as a human or a DAIDE-ish bot
would type it) into one of the frozen ``Order`` dataclasses from
``engine.types``. ``format_order`` is the inverse: it renders an ``Order``
back into a canonical string.

Design notes:

- There is exactly **one** tokenizer and **one** dispatch table here — no split
  by token length, no separate "short form" / "long form" code paths. Every
  order type funnels through the same tokenize → (optional power prefix) →
  dispatch-on-verb pipeline.
- Province names are resolved through ``MapData.aliases`` (lower-cased
  lookup) with a fallback to an already-canonical uppercase code. There is no
  separate alias table in this module.
- Coasts are recognised in both ``PROV/XX`` and ``PROV(XX)`` spellings. Armies
  may never carry a coast (rejected, not silently stripped). A fleet order
  naming a split-coast province with no coast is a parse-time ambiguity and is
  rejected here rather than deferred to validation.
- ``Order`` dataclasses (other than ``Build``) do not record which unit kind
  issued them — that is looked up from ``GameState`` at adjudication time.
  Consequently ``format_order`` cannot always recover the original "A"/"F"
  token for a non-split-coast province that can host either kind (e.g. a
  fleet holding at Brest prints as ``A BRE H``, not ``F BRE H``). This is
  round-trip safe because the parsed ``Order`` values compare equal either
  way; only the *human-facing* kind letter is lossy, and that loss is
  inherent to the ``Order`` model, not this module.
"""

from __future__ import annotations

import re
from typing import Optional

from engine.map_loader import MapData
from engine.types import (
    Build,
    Convoy,
    Disband,
    Hold,
    Location,
    Move,
    Order,
    Retreat,
    SupportHold,
    SupportMove,
    UnitKind,
    Waive,
)

__all__ = ["OrderParseError", "parse_order", "format_order"]


class OrderParseError(ValueError):
    """Raised when an order string does not conform to the grammar."""


_COAST_RE = re.compile(r"^([A-Z]+)(?:/([A-Z]{2})|\(([A-Z]{2})\))$")

_HOLD_WORDS = ("H", "HOLD", "HOLDS")
_SUPPORT_WORDS = ("S", "SUPPORT", "SUPPORTS")
_CONVOY_WORDS = ("C", "CONVOY", "CONVOYS")
_RETREAT_WORDS = ("R", "RETREAT")
_DISBAND_WORDS = ("D", "DISBAND")
_BUILD_WORDS = ("B", "BUILD")


def _tokenize(text: str) -> list[str]:
    """Split order text into uppercase tokens, treating ``-`` as its own token."""
    spaced = text.replace("-", " - ")
    return [tok.upper() for tok in spaced.split()]


def _strip_power_prefix(tokens: list[str], power: str, map: MapData) -> list[str]:
    """Drop an optional leading power-name token, e.g. ``FRANCE: A PAR - BUR``.

    Raises if the named power does not match ``power`` (the authoritative
    kwarg for the returned order).
    """
    if not tokens:
        return tokens
    first = tokens[0].rstrip(":")
    if first in map.home_centers:
        if first != power:
            raise OrderParseError(
                f"order is prefixed for {first} but power={power!r} was requested"
            )
        rest = tokens[1:]
        if rest and rest[0] == ":":
            rest = rest[1:]
        return rest
    return tokens


def _normalize_province(name: str, map: MapData) -> str:
    """Resolve a province token to its canonical code.

    A token that is *already* a canonical code wins outright, ahead of the
    alias table: at least one entry in the bundled standard map (Tyrolia)
    lists an alias-table "canonical" spelling that differs from the code
    actually used in the adjacency graph (``TRL`` vs. the real node ``TYR``).
    Preferring an exact, already-valid code sidesteps that kind of mismatch
    without special-casing it.
    """
    upper = name.upper()
    if upper in map.provinces:
        return upper
    canonical = map.aliases.get(name.lower())
    if canonical is not None:
        return canonical
    raise OrderParseError(f"unknown province: {name!r}")


def _split_coast_token(token: str) -> tuple[str, str | None]:
    match = _COAST_RE.match(token)
    if not match:
        return token, None
    name = match.group(1)
    coast = match.group(2) or match.group(3)
    return name, coast


def _require_build_coast(loc: Location, kind: UnitKind, map: MapData) -> None:
    """A fleet build on a split-coast province must name a coast (no source unit
    exists to infer it from, so an unspecified coast is irrecoverably ambiguous —
    DATC 6.B.14)."""
    if (
        kind is UnitKind.FLEET
        and loc.coast is None
        and map.is_split_coast(loc.province)
    ):
        raise OrderParseError(
            f"building a fleet at split-coast province {loc.province} must name a coast"
        )


def _parse_location(token: str, map: MapData, *, fleet: bool) -> Location:
    """Parse one province[/coast] token into a canonical ``Location``.

    ``fleet`` says whether the location names a fleet's own unit or a fleet
    destination/target (so coast rules apply) versus an army's (which may
    never carry a coast).
    """
    name, coast = _split_coast_token(token)
    canonical = _normalize_province(name, map)
    if coast is not None:
        if not fleet:
            # An army ignores a coast qualifier (DATC 6.B.12).
            coast = None
        elif not map.is_split_coast(canonical):
            # A coast on a single-coast province is meaningless; drop it.
            coast = None
        # Otherwise keep the coast as written. Whether it is actually a coast of
        # the province, and whether it is reachable, is decided by the
        # adjudicator/validation (one legality path) — a wrong or unspecified
        # coast becomes a VOID move, not a parse error.
    return Location(canonical, coast)


def parse_order(text: str, *, power: str, map: MapData) -> Order:
    """Parse one order string for ``power`` against ``map``'s topology.

    Raises ``OrderParseError`` on any grammar violation, unknown province, or
    parse-level coast ambiguity.
    """
    if not text or not text.strip():
        raise OrderParseError("empty order text")

    tokens = _tokenize(text.strip())
    tokens = _strip_power_prefix(tokens, power, map)

    if not tokens:
        raise OrderParseError("empty order text")

    if tokens == ["WAIVE"]:
        return Waive(power)

    # -- "D A PAR" (disband, verb-first) ------------------------------------
    if tokens[0] in _DISBAND_WORDS:
        if len(tokens) != 3 or tokens[1] not in ("A", "F"):
            raise OrderParseError("expected 'D A/F PROVINCE'")
        kind = UnitKind.ARMY if tokens[1] == "A" else UnitKind.FLEET
        loc = _parse_location(tokens[2], map, fleet=kind is UnitKind.FLEET)
        return Disband(power, unit=loc)

    # -- "BUILD A PAR" (build, verb-first) ----------------------------------
    if tokens[0] in _BUILD_WORDS:
        rest = tokens[1:]
        if len(rest) != 2 or rest[0] not in ("A", "F"):
            raise OrderParseError("expected 'BUILD A/F PROVINCE'")
        kind = UnitKind.ARMY if rest[0] == "A" else UnitKind.FLEET
        loc = _parse_location(rest[1], map, fleet=kind is UnitKind.FLEET)
        _require_build_coast(loc, kind, map)
        return Build(power, location=loc, kind=kind)

    # -- everything else starts with a unit: "A PAR ..." / "F BRE ..." -----
    if not tokens or tokens[0] not in ("A", "F"):
        got = tokens[0] if tokens else ""
        raise OrderParseError(f"expected unit kind 'A' or 'F', got {got!r}")
    if len(tokens) < 2:
        raise OrderParseError("missing unit location")

    kind = UnitKind.ARMY if tokens[0] == "A" else UnitKind.FLEET
    unit_loc = _parse_location(tokens[1], map, fleet=kind is UnitKind.FLEET)
    rest = tokens[2:]

    if not rest:
        raise OrderParseError(f"missing order verb after unit at {unit_loc}")

    verb = rest[0]

    if verb in _HOLD_WORDS:
        if len(rest) != 1:
            raise OrderParseError(f"malformed hold order: {text!r}")
        return Hold(power, unit=unit_loc)

    if verb in _DISBAND_WORDS:
        if len(rest) != 1:
            raise OrderParseError(f"malformed disband order: {text!r}")
        return Disband(power, unit=unit_loc)

    if verb in _BUILD_WORDS:
        if len(rest) != 1:
            raise OrderParseError(f"malformed build order: {text!r}")
        _require_build_coast(unit_loc, kind, map)
        return Build(power, location=unit_loc, kind=kind)

    if verb in _RETREAT_WORDS:
        dest_rest = rest[1:]
        if len(dest_rest) != 1:
            raise OrderParseError(f"malformed retreat order: {text!r}")
        dest = _parse_location(dest_rest[0], map, fleet=kind is UnitKind.FLEET)
        return Retreat(power, unit=unit_loc, dest=dest)

    if verb == "-":
        dest_rest = rest[1:]
        if not dest_rest:
            raise OrderParseError(f"move order missing destination: {text!r}")
        dest = _parse_location(dest_rest[0], map, fleet=kind is UnitKind.FLEET)
        tail = dest_rest[1:]
        via = False
        if tail:
            if tail[0] != "VIA":
                raise OrderParseError(f"unexpected trailing tokens: {tail!r}")
            via = True
            tail2 = tail[1:]
            if tail2 and tail2 != ["CONVOY"]:
                raise OrderParseError(f"unexpected trailing tokens: {tail2!r}")
        return Move(power, unit=unit_loc, dest=dest, via_convoy=via)

    if verb in _SUPPORT_WORDS:
        sub = rest[1:]
        if len(sub) < 2 or sub[0] not in ("A", "F"):
            raise OrderParseError(f"malformed support order: {text!r}")
        sub_kind = UnitKind.ARMY if sub[0] == "A" else UnitKind.FLEET
        origin = _parse_location(sub[1], map, fleet=sub_kind is UnitKind.FLEET)
        sub_rest = sub[2:]
        if not sub_rest:
            return SupportHold(power, unit=unit_loc, target=origin)
        if sub_rest[0] == "-" and len(sub_rest) == 2:
            dest = _parse_location(sub_rest[1], map, fleet=sub_kind is UnitKind.FLEET)
            return SupportMove(power, unit=unit_loc, origin=origin, dest=dest)
        raise OrderParseError(f"malformed support order: {text!r}")

    if verb in _CONVOY_WORDS:
        sub = rest[1:]
        if len(sub) < 2 or sub[0] != "A":
            raise OrderParseError(f"malformed convoy order (must carry an army): {text!r}")
        origin = _parse_location(sub[1], map, fleet=False)
        sub_rest = sub[2:]
        if len(sub_rest) != 2 or sub_rest[0] != "-":
            raise OrderParseError(f"malformed convoy order: {text!r}")
        dest = _parse_location(sub_rest[1], map, fleet=False)
        return Convoy(power, unit=unit_loc, origin=origin, dest=dest)

    raise OrderParseError(f"unrecognized order verb: {verb!r}")


def _kind_letter(loc: Location, kind_by_province: Optional[dict[str, str]] = None) -> str:
    """Display kind for ``loc``: the board unit's actual kind when known via
    ``kind_by_province`` (province code → ``"A"``/``"F"``), else ``F`` if ``loc``
    names a coast, else ``A``.

    Without a board map this is round-trip safe but not truth-preserving for
    non-split-coast provinces that can host either kind (see the module docstring);
    passing ``kind_by_province`` makes it truthful for display.
    """
    if kind_by_province is not None:
        kind = kind_by_province.get(loc.province)
        if kind is not None:
            return kind
    return "F" if loc.coast is not None else "A"


def _unit_str(loc: Location, kind_by_province: Optional[dict[str, str]] = None) -> str:
    return f"{_kind_letter(loc, kind_by_province)} {loc}"


def format_order(
    order: Order, kind_by_province: Optional[dict[str, str]] = None
) -> str:
    """Render ``order`` as a canonical order string (no power prefix).

    ``kind_by_province`` (province code → ``"A"``/``"F"``) makes the unit letters
    truthful for human display; without it the letter is inferred from coast
    presence (round-trip safe, but a fleet at a non-split province prints ``A``).
    """
    def u(loc: Location) -> str:
        return _unit_str(loc, kind_by_province)

    if isinstance(order, Waive):
        return "WAIVE"
    if isinstance(order, Hold):
        return f"{u(order.unit)} H"
    if isinstance(order, Move):
        text = f"{u(order.unit)} - {order.dest}"
        return f"{text} VIA" if order.via_convoy else text
    if isinstance(order, SupportHold):
        return f"{u(order.unit)} S {u(order.target)}"
    if isinstance(order, SupportMove):
        return f"{u(order.unit)} S {u(order.origin)} - {order.dest}"
    if isinstance(order, Convoy):
        return f"{u(order.unit)} C {u(order.origin)} - {order.dest}"
    if isinstance(order, Retreat):
        return f"{u(order.unit)} R {order.dest}"
    if isinstance(order, Disband):
        return f"D {u(order.unit)}"
    if isinstance(order, Build):
        kind_letter = "A" if order.kind is UnitKind.ARMY else "F"
        return f"BUILD {kind_letter} {order.location}"
    raise TypeError(f"unknown order type: {order!r}")
