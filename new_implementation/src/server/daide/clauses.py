"""The encode/decode bridge between DAIDE token-stream clauses and `engine.types`.

This is the analogue, for the wire protocol, of `engine.orders.parser`: that module
bridges human order *text* to `Order` objects; this module bridges DAIDE *token*
clauses to the same objects. Still no I/O (only the `engine.map_loader` calls a
caller passes a `MapData` for -- this module itself does no file access), so it
stays importable and testable without a DB or network, matching D1's `tokens.py`
and `wire.py`.

Clause shapes below are dictated by the external DAIDE specification (cross-checked
against `old_implementation/diplomacy/daide/clauses.py`, read-only, per Track D's
Ground Rules in `docs/specs/done_fixes.md` -- not copied; the byte-level shapes are
the compliance requirement, the code here is original):

- A **province** with no coast is a single token (``PAR``). A province that
  *needs* a coast (a fleet at a split-coast province) is a 2-token group
  ``(PROV COAST)``.
- A **unit** is the 3-token group ``(POWER AMY|FLT PROVINCE-CLAUSE)`` -- note
  the province clause nests its own parens when it carries a coast, e.g.
  ``(RUS FLT (STP SC))``.
- A **turn** is the group ``(SEASON YEAR)``.
- An **order clause** is always exactly one outer ``( ... )`` group wrapping
  either a unit clause + order-type + arguments, or (for ``WVE``) a bare power
  token + ``WVE``. This one-group-per-order convention is what lets a `SUB`
  message (D4's job) simply concatenate order clauses.

## Design decisions worth flagging up front

- **Decode goes through `engine.orders.parser.parse_order`.** Once a DAIDE order
  clause's tokens are unpacked into unit kind/location/power and any sub-unit or
  destination, this module renders the same order-string grammar `parse_order`
  already accepts (``"A PAR - BUR"``, ``"F STP/SC S A PAR"``, ...) and calls it,
  rather than re-implementing coast/VIA/alias validation a second time.
- **Encode does *not* go through `format_order`.** `format_order` produces a
  string with no notion of a *foreign* unit's owning power (DAIDE's `SUP`/`CVY`
  clauses need one for the *target*/`origin` unit, which `SupportHold`/
  `SupportMove`/`Convoy` do not record at all -- only `Location`), and every
  `Location` here is already a canonical, validated engine value with no
  parsing left to do. Routing encode through a string only to re-derive the
  same locations/kinds from it would add a text round-trip for no reuse
  benefit. Encode instead composes tokens directly from the `Order` dataclass's
  own fields, using the same `kind_by_province` convention `format_order` uses
  for the "which letter does this location actually hold" ambiguity (see
  `docs/specs/fix_plan.md`'s Track A PR2 "Two findings" note), plus an
  analogous `power_by_province` for the foreign-unit-power problem above (DAIDE
  reserves the ``UNO`` token -- "unknown power" -- for exactly this case; encode
  falls back to it when no lookup is supplied or the lookup misses).
- **`Move.via_convoy`'s fleet path is not engine state.** The engine's `Move`
  order carries only a bool; the actual convoying fleets are separate `Convoy`
  orders submitted by their owners. Decoding ``CTO dest VIA (f1 f2 ...)``
  therefore produces `Move(unit, dest, via_convoy=True)` and only *validates*
  that the parenthesized list is well-formed province tokens (a malformed VIA
  list is a decode error) without threading the path through as state.
  Encoding the reverse takes an optional `via_fleets` sequence (the caller --
  D4, which has the whole phase's orders -- can supply the real fleet
  provinces from the matching `Convoy` orders); with none supplied this emits
  a syntactically valid but empty ``VIA ()`` group.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from engine.map_loader import MapData
from engine.orders.parser import parse_order
from engine.types import (
    Build,
    Convoy,
    Disband,
    Hold,
    Location,
    Move,
    Order,
    PhaseType,
    Retreat,
    Season,
    SupportHold,
    SupportMove,
    Unit,
    UnitKind,
    Waive,
)
from server.daide import tokens as t
from server.daide.tokens import Token

__all__ = [
    "Clause",
    "ClauseDecodeError",
    "location_to_clause",
    "location_from_clause",
    "unit_to_clause",
    "unit_from_clause",
    "engine_to_turn_token",
    "turn_token_to_engine",
    "turn_clause",
    "turn_from_clause",
    "decode_order",
    "encode_order",
]

# A DAIDE clause is just a flat token sequence -- groups are expressed with
# `OPEN_PAREN`/`CLOSE_PAREN` tokens inline, exactly as they appear on the wire.
Clause = tuple[Token, ...]


class ClauseDecodeError(ValueError):
    """A DAIDE token clause does not conform to the shape this module expects.

    Subclasses `ValueError` (matching `engine.orders.parser.OrderParseError`'s
    convention) so callers that already catch `ValueError` from the vocabulary
    lookups in `tokens.py` (unknown province/power/coast token) don't need a
    second except clause for clause-shape errors.
    """


# ---------------------------------------------------------------------------
# Small internal helpers
# ---------------------------------------------------------------------------


def _read_group(tokens_: Sequence[Token]) -> tuple[list[Token], int]:
    """``tokens_[0]`` must be ``(``. Returns (inner tokens, tokens consumed).

    Handles nesting (a province-with-coast group inside a unit group inside an
    order group) by tracking paren depth rather than assuming a flat scan.
    """
    if not tokens_ or tokens_[0] != t.OPEN_PAREN:
        raise ClauseDecodeError("expected a '(' to start a group")
    depth = 0
    for i, token in enumerate(tokens_):
        if token == t.OPEN_PAREN:
            depth += 1
        elif token == t.CLOSE_PAREN:
            depth -= 1
            if depth == 0:
                return list(tokens_[1:i]), i + 1
    raise ClauseDecodeError("unterminated '(' group")


def _require_exhausted(tokens_: Sequence[Token]) -> None:
    if tokens_:
        raise ClauseDecodeError(
            f"unexpected trailing tokens in clause: {[tok.text for tok in tokens_]!r}"
        )


def _resolve_kind(loc: Location, kind_by_province: Optional[dict[str, str]]) -> UnitKind:
    """The unit kind standing at ``loc`` for encoding purposes.

    Same convention `engine.orders.parser.format_order` uses: trust
    ``kind_by_province`` when supplied (the caller has real board state),
    otherwise infer from coast presence (right for a fleet at a split-coast
    province, wrong -- but round-trip-safe -- for a fleet at a non-split one).
    """
    if kind_by_province is not None:
        letter = kind_by_province.get(loc.province)
        if letter is not None:
            return UnitKind.ARMY if letter == "A" else UnitKind.FLEET
    return UnitKind.FLEET if loc.coast is not None else UnitKind.ARMY


def _resolve_power_token(loc: Location, power_by_province: Optional[dict[str, str]]) -> Token:
    """The DAIDE power token for whoever owns the unit at ``loc``, or ``UNO``
    ("unknown power") when the caller didn't supply a lookup or it missed."""
    if power_by_province is not None:
        name = power_by_province.get(loc.province)
        if name is not None:
            return t.POWER_TOKEN_BY_ENGINE_NAME[name]
    return t.UNO


def _power_name_or_unknown(token: Token) -> str:
    """`tokens.engine_power_name`, but tolerant of the ``UNO`` placeholder.

    Only sub-units (a `SUP`/`CVY` clause's target/origin) may legitimately
    carry ``UNO`` -- the engine's `SupportHold`/`SupportMove`/`Convoy` orders
    don't record the target's power at all, so decode never actually uses this
    string; it exists only so `unit_from_clause` can build a `Unit` value for
    every clause shape without a special case at the call site.
    """
    if token == t.UNO:
        return "UNO"
    return t.engine_power_name(token)


# ---------------------------------------------------------------------------
# Province + optional coast <-> Location
# ---------------------------------------------------------------------------


def location_to_clause(loc: Location) -> Clause:
    """``Location`` -> DAIDE tokens: a bare province token, or a ``(PROV COAST)``
    group when the location carries a coast."""
    province_token = t.daide_province_token(loc.province)
    if loc.coast is None:
        return (province_token,)
    coast_token = t.COAST_TOKEN_BY_ENGINE_SUFFIX[loc.coast]
    return (t.OPEN_PAREN, province_token, coast_token, t.CLOSE_PAREN)


def location_from_clause(
    tokens_: Sequence[Token], *, map: MapData, fleet: bool
) -> tuple[Location, int]:
    """Parse a province[+coast] clause starting at ``tokens_[0]``.

    Returns ``(Location, tokens consumed)`` so callers parsing a longer clause
    (an order's destination, say) know where the next token starts.

    ``fleet`` says whether the *owner* of this location is a fleet -- this
    drives two checks the task calls out explicitly: a coast token attached to
    a province `map` doesn't consider split-coast is always a decode error
    (regardless of unit kind); a *missing* coast for a fleet standing in a
    split-coast province is also a decode error (an army there, or a bare
    reference to the province as a whole, is fine without one).
    """
    if not tokens_:
        raise ClauseDecodeError("expected a province clause, got nothing")

    if tokens_[0] == t.OPEN_PAREN:
        inner, consumed = _read_group(tokens_)
        if len(inner) != 2:
            raise ClauseDecodeError(
                f"a province+coast group must be '(' province coast ')', got {inner!r}"
            )
        province_token, coast_token = inner
        province = t.engine_province_code(province_token)
        coast = t.engine_coast_suffix(coast_token)
        if not map.is_split_coast(province):
            raise ClauseDecodeError(
                f"{province} is not a split-coast province; it may not carry a coast token"
            )
        if coast not in map.coasts_of(province):
            raise ClauseDecodeError(
                f"{coast} is not one of {province}'s coasts ({map.coasts_of(province)})"
            )
        if not fleet:
            raise ClauseDecodeError(
                f"an army location may not carry a coast (got {province}/{coast})"
            )
        return Location(province, coast), consumed

    province = t.engine_province_code(tokens_[0])
    if fleet and map.is_split_coast(province):
        raise ClauseDecodeError(f"a fleet at split-coast province {province} must name a coast")
    return Location(province, None), 1


# ---------------------------------------------------------------------------
# Unit (type + location, + power for the DAIDE wire shape) <-> engine.types.Unit
# ---------------------------------------------------------------------------


def unit_to_clause(unit: Unit) -> Clause:
    """``Unit`` -> the DAIDE unit group ``(POWER AMY|FLT PROVINCE-CLAUSE)``."""
    power_token = t.POWER_TOKEN_BY_ENGINE_NAME.get(unit.power, t.UNO)
    kind_token = t.AMY if unit.kind is UnitKind.ARMY else t.FLT
    return (
        (t.OPEN_PAREN, power_token, kind_token)
        + location_to_clause(unit.location)
        + (t.CLOSE_PAREN,)
    )


def unit_from_clause(tokens_: Sequence[Token], *, map: MapData) -> tuple[Unit, int]:
    """Parse a unit group starting at ``tokens_[0]``. Returns ``(Unit, tokens consumed)``.

    ``unit.power`` is the string ``"UNO"`` when the clause carried DAIDE's
    "unknown power" placeholder -- legitimate for a `SUP`/`CVY` sub-unit, never
    for the order's own unit (`decode_order` rejects that case explicitly).
    """
    inner, consumed = _read_group(tokens_)
    if len(inner) < 3:
        raise ClauseDecodeError(f"a unit clause needs power, type, and a province: got {inner!r}")
    power_token, kind_token, *loc_tokens = inner
    power_name = _power_name_or_unknown(power_token)
    if kind_token == t.AMY:
        kind = UnitKind.ARMY
    elif kind_token == t.FLT:
        kind = UnitKind.FLEET
    else:
        raise ClauseDecodeError(f"expected AMY or FLT in unit clause, got {kind_token.text!r}")
    location, loc_consumed = location_from_clause(loc_tokens, map=map, fleet=kind is UnitKind.FLEET)
    _require_exhausted(loc_tokens[loc_consumed:])
    return Unit(kind=kind, power=power_name, location=location), consumed


# ---------------------------------------------------------------------------
# Turn/season <-> (Season, PhaseType)
# ---------------------------------------------------------------------------
#
# DAIDE names 5 phase tokens per year; this engine folds the same 5 real phases
# into 3 seasons x 3 phase-types (only 5 of the 9 combinations occur). DAIDE
# gives the retreat sub-phase of spring/fall its own token instead of a
# separate "phase type" axis -- SUM is spring's retreats, AUT is fall's -- so
# the mapping is a straight lookup table, not a formula:
#
#   SPR <-> (SPRING, MOVEMENT)      -- spring moves
#   SUM <-> (SPRING, RETREAT)       -- spring retreats
#   FAL <-> (FALL,   MOVEMENT)      -- fall moves
#   AUT <-> (FALL,   RETREAT)       -- fall retreats
#   WIN <-> (WINTER, ADJUSTMENT)    -- builds/disbands (winter has no movement
#                                      or retreat phase at all)

_TURN_TOKEN_TO_ENGINE: dict[str, tuple[Season, PhaseType]] = {
    "SPR": (Season.SPRING, PhaseType.MOVEMENT),
    "SUM": (Season.SPRING, PhaseType.RETREAT),
    "FAL": (Season.FALL, PhaseType.MOVEMENT),
    "AUT": (Season.FALL, PhaseType.RETREAT),
    "WIN": (Season.WINTER, PhaseType.ADJUSTMENT),
}
_ENGINE_TO_TURN_TOKEN: dict[tuple[Season, PhaseType], str] = {
    v: k for k, v in _TURN_TOKEN_TO_ENGINE.items()
}


def turn_token_to_engine(token: Token) -> tuple[Season, PhaseType]:
    """A DAIDE season token (``SPR``/``SUM``/``FAL``/``AUT``/``WIN``) -> ``(Season, PhaseType)``."""
    try:
        return _TURN_TOKEN_TO_ENGINE[token.text]
    except KeyError:
        raise ClauseDecodeError(f"{token.text!r} is not a DAIDE season/turn token") from None


def engine_to_turn_token(season: Season, phase_type: PhaseType) -> Token:
    """``(Season, PhaseType)`` -> its DAIDE season token, for one of the 5 real phases."""
    try:
        text = _ENGINE_TO_TURN_TOKEN[(season, phase_type)]
    except KeyError:
        raise ValueError(
            f"({season}, {phase_type}) is not one of the 5 phases DAIDE has a turn token for"
        ) from None
    return Token.from_str(text)


def turn_clause(season: Season, phase_type: PhaseType, year: int) -> Clause:
    """``(Season, PhaseType, year)`` -> the DAIDE turn group ``(SEASON YEAR)``."""
    return (
        t.OPEN_PAREN,
        engine_to_turn_token(season, phase_type),
        Token.from_int(year),
        t.CLOSE_PAREN,
    )


def turn_from_clause(tokens_: Sequence[Token]) -> tuple[Season, PhaseType, int]:
    """Parse a turn group. Expects exactly ``(`` season year ``)`` -- 4 tokens, no more."""
    if len(tokens_) != 4 or tokens_[0] != t.OPEN_PAREN or tokens_[3] != t.CLOSE_PAREN:
        raise ClauseDecodeError(
            f"a turn clause is '(' season year ')', got {[tok.text for tok in tokens_]!r}"
        )
    season, phase_type = turn_token_to_engine(tokens_[1])
    if not tokens_[2].is_integer:
        raise ClauseDecodeError(
            f"expected an integer year token in the turn clause, got {tokens_[2].text!r}"
        )
    return season, phase_type, int(tokens_[2])


# ---------------------------------------------------------------------------
# Order clauses <-> engine.types.Order
# ---------------------------------------------------------------------------


def _unit_order_text(kind: UnitKind, loc: Location) -> str:
    return f"{'A' if kind is UnitKind.ARMY else 'F'} {loc}"


def decode_order(clause: Sequence[Token], *, phase_type: PhaseType, map: MapData) -> Order:
    """A full DAIDE order clause -> the `Order` `engine.orders.parser.parse_order`
    would build from the equivalent order string.

    ``clause`` is one whole order: exactly one outer ``(`` ... ``)`` group (see
    the module docstring for why every order is wrapped this way). ``phase_type``
    disambiguates ``DSB`` (retreat-phase disband) from ``REM`` (adjustment-phase
    remove) -- both decode to the same `Disband` order, but seeing one in the
    wrong phase context is a genuine protocol violation, not something to
    silently accept.
    """
    tokens_ = list(clause)
    if len(tokens_) < 2 or tokens_[0] != t.OPEN_PAREN or tokens_[-1] != t.CLOSE_PAREN:
        raise ClauseDecodeError("an order clause must be exactly one '(' ... ')' group")
    body = tokens_[1:-1]
    if not body:
        raise ClauseDecodeError("empty order clause")

    if body[0] != t.OPEN_PAREN:
        # "(power WVE)" -- the one order type with no unit clause at all.
        if len(body) == 2 and body[1] == t.WVE:
            power = t.engine_power_name(body[0])
            return Waive(power)
        raise ClauseDecodeError(
            f"expected a unit clause or a bare 'power WVE' clause, got {body!r}"
        )

    unit, consumed = unit_from_clause(body, map=map)
    if unit.power == "UNO":
        raise ClauseDecodeError("an order's own unit must name a real power, not UNO")
    rest = body[consumed:]
    if not rest:
        raise ClauseDecodeError("order clause is missing an order-type token after its unit")
    verb, *args = rest
    unit_text = _unit_order_text(unit.kind, unit.location)

    if verb == t.HLD:
        _require_exhausted(args)
        text = f"{unit_text} H"

    elif verb == t.MTO:
        dest, n = location_from_clause(args, map=map, fleet=unit.kind is UnitKind.FLEET)
        _require_exhausted(args[n:])
        text = f"{unit_text} - {dest}"

    elif verb == t.CTO:
        dest, n = location_from_clause(args, map=map, fleet=unit.kind is UnitKind.FLEET)
        tail = args[n:]
        if tail:
            if tail[0] != t.VIA:
                raise ClauseDecodeError(
                    f"expected VIA after a CTO destination, got {tail[0].text!r}"
                )
            via_rest = tail[1:]
            if not via_rest or via_rest[0] != t.OPEN_PAREN:
                raise ClauseDecodeError(
                    "VIA must be followed by a parenthesized list of convoying fleets"
                )
            fleet_group, n2 = _read_group(via_rest)
            for prov_token in fleet_group:
                t.engine_province_code(
                    prov_token
                )  # validate shape; the path itself is not engine state
            _require_exhausted(via_rest[n2:])
        text = f"{unit_text} - {dest} VIA"

    elif verb == t.SUP:
        sub_unit, n = unit_from_clause(args, map=map)
        tail = args[n:]
        sub_text = _unit_order_text(sub_unit.kind, sub_unit.location)
        if not tail:
            text = f"{unit_text} S {sub_text}"
        else:
            if tail[0] != t.MTO:
                raise ClauseDecodeError(
                    f"expected MTO in a support-move clause, got {tail[0].text!r}"
                )
            dest, n2 = location_from_clause(
                tail[1:], map=map, fleet=sub_unit.kind is UnitKind.FLEET
            )
            _require_exhausted(tail[1 + n2 :])
            text = f"{unit_text} S {sub_text} - {dest}"

    elif verb == t.CVY:
        sub_unit, n = unit_from_clause(args, map=map)
        if sub_unit.kind is not UnitKind.ARMY:
            raise ClauseDecodeError("only an army may be convoyed")
        tail = args[n:]
        if not tail or tail[0] != t.CTO:
            raise ClauseDecodeError("expected CTO in a convoy clause")
        dest, n2 = location_from_clause(tail[1:], map=map, fleet=False)
        _require_exhausted(tail[1 + n2 :])
        text = f"{unit_text} C A {sub_unit.location} - {dest}"

    elif verb == t.RTO:
        dest, n = location_from_clause(args, map=map, fleet=unit.kind is UnitKind.FLEET)
        _require_exhausted(args[n:])
        text = f"{unit_text} R {dest}"

    elif verb == t.DSB:
        if phase_type is not PhaseType.RETREAT:
            raise ClauseDecodeError("DSB is only valid in a retreat phase (adjustment uses REM)")
        _require_exhausted(args)
        text = f"D {unit_text}"

    elif verb == t.REM:
        if phase_type is not PhaseType.ADJUSTMENT:
            raise ClauseDecodeError("REM is only valid in an adjustment phase (retreat uses DSB)")
        _require_exhausted(args)
        text = f"D {unit_text}"

    elif verb == t.BLD:
        _require_exhausted(args)
        text = f"BUILD {unit_text}"

    else:
        raise ClauseDecodeError(f"unrecognized order-type token {verb.text!r}")

    return parse_order(text, power=unit.power, map=map)


def encode_order(
    order: Order,
    *,
    phase_type: PhaseType,
    map: MapData,
    kind_by_province: Optional[dict[str, str]] = None,
    power_by_province: Optional[dict[str, str]] = None,
    via_fleets: Sequence[Location] = (),
) -> Clause:
    """``Order`` -> the DAIDE order clause `decode_order` would decode back to it.

    ``kind_by_province`` (engine province -> ``"A"``/``"F"``) resolves the
    order's own unit kind the same way `format_order` needs it -- without it, a
    fleet at a non-split-coast province encodes as ``AMY`` (coast-presence
    heuristic, round-trip-safe but not truthful; see the module docstring).

    ``power_by_province`` resolves the *owning power* of a `SUP`/`SupportMove`
    target or a `Convoy` origin -- information the engine's order types don't
    carry at all. Missing an entry (or omitting the map) encodes DAIDE's
    ``UNO`` ("unknown power") token there instead, which is a legitimate,
    spec-sanctioned placeholder, not a lossy hack.

    ``via_fleets`` supplies the convoying fleets' provinces for a
    ``Move(via_convoy=True)`` order's ``VIA (...)`` list -- the engine's `Move`
    doesn't retain this path (see module docstring); omitting it produces a
    syntactically valid but empty ``VIA ()`` group.
    """
    if isinstance(order, Waive):
        power_token = t.POWER_TOKEN_BY_ENGINE_NAME[order.power]
        return (t.OPEN_PAREN, power_token, t.WVE, t.CLOSE_PAREN)

    if isinstance(order, Build):
        own_loc, own_kind = order.location, order.kind
    else:
        own_loc = order.unit  # every remaining Order variant names its own unit here
        own_kind = _resolve_kind(own_loc, kind_by_province)
    own_unit = Unit(kind=own_kind, power=order.power, location=own_loc)
    unit_tokens = unit_to_clause(own_unit)

    if isinstance(order, Hold):
        body = unit_tokens + (t.HLD,)

    elif isinstance(order, Move):
        dest_tokens = location_to_clause(order.dest)
        if order.via_convoy:
            fleet_tokens: Clause = ()
            for loc in via_fleets:
                fleet_tokens += (t.daide_province_token(loc.province),)
            body = (
                unit_tokens
                + (t.CTO,)
                + dest_tokens
                + (t.VIA, t.OPEN_PAREN)
                + fleet_tokens
                + (t.CLOSE_PAREN,)
            )
        else:
            body = unit_tokens + (t.MTO,) + dest_tokens

    elif isinstance(order, SupportHold):
        target_kind = _resolve_kind(order.target, kind_by_province)
        target_power = _resolve_power_token(order.target, power_by_province)
        target_unit_tokens = (
            (t.OPEN_PAREN, target_power, t.AMY if target_kind is UnitKind.ARMY else t.FLT)
            + location_to_clause(order.target)
            + (t.CLOSE_PAREN,)
        )
        body = unit_tokens + (t.SUP,) + target_unit_tokens

    elif isinstance(order, SupportMove):
        origin_kind = _resolve_kind(order.origin, kind_by_province)
        origin_power = _resolve_power_token(order.origin, power_by_province)
        origin_unit_tokens = (
            (t.OPEN_PAREN, origin_power, t.AMY if origin_kind is UnitKind.ARMY else t.FLT)
            + location_to_clause(order.origin)
            + (t.CLOSE_PAREN,)
        )
        dest_tokens = location_to_clause(order.dest)
        body = unit_tokens + (t.SUP,) + origin_unit_tokens + (t.MTO,) + dest_tokens

    elif isinstance(order, Convoy):
        origin_power = _resolve_power_token(order.origin, power_by_province)
        origin_unit_tokens = (
            (t.OPEN_PAREN, origin_power, t.AMY)
            + location_to_clause(order.origin)
            + (t.CLOSE_PAREN,)
        )
        dest_tokens = location_to_clause(order.dest)
        body = unit_tokens + (t.CVY,) + origin_unit_tokens + (t.CTO,) + dest_tokens

    elif isinstance(order, Retreat):
        dest_tokens = location_to_clause(order.dest)
        body = unit_tokens + (t.RTO,) + dest_tokens

    elif isinstance(order, Disband):
        verb = t.DSB if phase_type is PhaseType.RETREAT else t.REM
        body = unit_tokens + (verb,)

    elif isinstance(order, Build):
        body = unit_tokens + (t.BLD,)

    else:  # pragma: no cover - exhaustive over engine.types.Order's variants
        raise TypeError(f"unknown order type: {order!r}")

    return (t.OPEN_PAREN,) + body + (t.CLOSE_PAREN,)
