"""Order helpers: why an order is impossible, or what it depends on.

Pure module, the sibling of ``legal_orders``: no FastAPI, no DB, no
``game_service`` import. It takes a ``MapData``, a ``GameState``, a power and
that power's **own** orders, and returns plain data, so the API, the web game
page and the Telegram bot all say the same thing.

Nothing here ever sees another power's pending orders -- the signature has no
room for them. Every note is computed from the board (which every player sees)
and the requesting power's own orders, so a note can name a foreign fleet that
*could* convoy an army, but never says whether it has been ordered to.

Two kinds of note (``{"kind": ..., "text": ...}``):

- ``impossible`` -- the order is refused, or is accepted but cannot succeed
  whatever anyone orders; the text says why and what would work instead.
- ``warning`` -- the order is accepted, but its success depends on something
  the player can see in their own orders or on the board: a convoy nobody of
  theirs has ordered, a support for a unit of theirs ordered to do something
  else, two of their units ordered into one province, a support for an attack
  on their own unit, or a unit left without an order.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from engine.adjudicator.movement import convoy_route_possible
from engine.adjudicator.retreats import retreat_refusal
from engine.map_loader import MapData
from engine.orders.parser import OrderParseError, format_order, parse_order
from engine.orders.validation import legal_builds, validate
from server.legal_orders import adjustments_owed
from engine.types import (
    Build,
    Convoy,
    Disband,
    GameState,
    GameStatus,
    Hold,
    Location,
    Move,
    Order,
    PhaseType,
    ProvinceType,
    Retreat,
    SupportHold,
    SupportMove,
    Unit,
    UnitKind,
    Waive,
)

__all__ = ["IMPOSSIBLE", "WARNING", "convoy_routes", "order_notes", "own_unit_support_note"]

IMPOSSIBLE = "impossible"
WARNING = "warning"

# Longest fleet chain searched for, and how many alternative routes a note names.
_MAX_CHAIN = 8
_MAX_ROUTES_SHOWN = 3


def own_unit_support_note(kind: str, location: Location) -> str:
    """The note for a support of a move onto the power's own unit (DATC 6.D.10)."""
    return f"your own {kind} {location} is there: this support has no effect unless it moves away"


def order_notes(
    map: MapData, state: GameState, power: str, orders: Sequence[str]
) -> dict[str, Any]:
    """Helper notes for ``power``'s own ``orders`` in the current phase.

    ``orders`` is the power's whole order set as the player has it (stored or
    drafted); a later valid order for a unit replaces an earlier one, as on
    submission. Returns::

        {
          "orders": [{"order": "A LON - NWY", "ok": True,
                      "notes": [{"kind": "warning", "text": "..."}]}],
          "notes": [{"kind": "warning", "text": "A PAR has no order, so it will hold"}],
        }

    ``orders`` has one entry per non-blank input, in input order; ``ok`` is
    whether the order passes validation (an order that does not parse has
    ``ok`` false and no notes -- its parse error says enough). ``notes`` at the
    top level is about the set as a whole (units left without an order, builds
    or disbands not yet given).
    """
    power = power.upper()
    if state.status is GameStatus.COMPLETED:
        return {
            "orders": [{"order": o.strip(), "ok": False, "notes": []} for o in orders if o.strip()],
            "notes": [],
        }
    kinds = _kinds(state)
    parsed: list[tuple[str, Order | None, bool]] = []
    own: dict[str, Order] = {}  # unit (or build site) province -> its valid order
    waives = 0
    for raw in orders:
        raw = raw.strip()
        if not raw:
            continue
        try:
            order = parse_order(raw, power=power, map=map)
        except OrderParseError:
            parsed.append((raw, None, False))
            continue
        ok = validate(order, state, map).ok
        parsed.append((raw, order, ok))
        if ok:
            key = _key(order)
            if key is None:
                waives += 1
            else:
                own[key] = order

    ctx = _Context(map, state, power, kinds, own)
    entries = []
    for raw, order, ok in parsed:
        notes: list[dict[str, str]] = []
        if order is not None:
            notes = ctx.accepted_notes(order) if ok else ctx.refused_notes(order)
        entries.append({"order": raw, "ok": ok, "notes": notes})
    return {"orders": entries, "notes": ctx.set_notes(waives)}


def convoy_routes(map: MapData, state: GameState, src: str, dst: str) -> list[tuple[Unit, ...]]:
    """The fleet chains on the board that could convoy an army ``src`` -> ``dst``.

    Each route is a chain of fleets in sea provinces (any power), no fleet
    twice, from one touching ``src`` to one touching ``dst``: the same possible
    route the adjudicator looks for (``convoy_route_possible``). Only minimal
    routes are returned -- none whose fleets include another route's -- shortest
    first, then by province. Empty means no convoy can carry the army there.
    """
    sea = {
        u.province: u
        for u in state.units
        if u.kind is UnitKind.FLEET and map.province_type(u.province) is ProvinceType.WATER
    }

    def touches(p: str, province: str) -> bool:
        return any(d.province == province for d in map.fleet_moves(sea[p].location))

    found: set[frozenset[str]] = set()

    def walk(path: list[str]) -> None:
        last = path[-1]
        if touches(last, dst):
            found.add(frozenset(path))
            return  # a longer chain through here only adds fleets
        if len(path) >= _MAX_CHAIN:
            return
        for nxt in sorted(sea):
            if nxt not in path and map.is_adjacent(
                sea[last].location, sea[nxt].location, UnitKind.FLEET
            ):
                walk([*path, nxt])

    for start in sorted(p for p in sea if touches(p, src)):
        walk([start])
    minimal = [r for r in found if not any(o < r for o in found)]
    minimal.sort(key=lambda r: (len(r), sorted(r)))
    return [tuple(sea[p] for p in sorted(r)) for r in minimal]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _kinds(state: GameState) -> dict[str, str]:
    out = {u.province: u.kind.value for u in state.units}
    for du in state.dislodged:
        out[du.unit.province] = du.unit.kind.value
    return out


def _key(order: Order) -> str | None:
    if isinstance(order, Waive):
        return None
    if isinstance(order, Build):
        return order.location.province
    return order.unit.province  # type: ignore[attr-defined]


def _note(kind: str, code: str, text: str) -> dict[str, str]:
    return {"kind": kind, "code": code, "text": text}


def _join(items: Sequence[str], word: str = "or") -> str:
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} {word} {items[-1]}"


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


class _Context:
    """One power's board and own orders, for the note functions."""

    def __init__(
        self,
        map: MapData,
        state: GameState,
        power: str,
        kinds: dict[str, str],
        own: dict[str, Order],
    ) -> None:
        self.map = map
        self.state = state
        self.power = power
        self.kinds = kinds
        self.own = own

    # -- naming --------------------------------------------------------------

    def label(self, unit: Unit) -> str:
        """A unit as the UI names it: ``F NTH`` for the player's own, ``England's F NTH`` otherwise."""
        name = f"{unit.kind.value} {unit.location}"
        return name if unit.power == self.power else f"{unit.power.title()}'s {name}"

    def show(self, order: Order) -> str:
        return format_order(order, self.kinds)

    def unit(self, province: str) -> Unit | None:
        return self.state.unit_at(province)

    # -- refused orders --------------------------------------------------------

    def refused_notes(self, order: Order) -> list[dict[str, str]]:
        if isinstance(order, Retreat):
            return self._refused_retreat(order)
        if isinstance(order, Build):
            return self._refused_build(order)
        if isinstance(order, (Hold, Move, SupportHold, SupportMove, Convoy)):
            if self.state.phase_type is not PhaseType.MOVEMENT:
                return []
            unit = self.unit(order.unit.province)
            if unit is None or unit.power != self.power:
                return []
            if isinstance(order, Move):
                return self._refused_move(order, unit)
            if isinstance(order, (SupportHold, SupportMove)):
                return self._refused_support(order, unit)
            if isinstance(order, Convoy):
                return self._refused_convoy(order, unit)
        return []

    def _refused_move(self, order: Move, unit: Unit) -> list[dict[str, str]]:
        dest = order.dest
        dest_type = self.map.province_type(dest.province)
        name = self.label(unit)
        if unit.kind is UnitKind.FLEET:
            if order.via_convoy:
                return [
                    _note(
                        IMPOSSIBLE,
                        "not_an_army",
                        f"only an army can be convoyed; {name} has to move on its own",
                    )
                ]
            if dest_type is ProvinceType.LAND:
                return [
                    _note(
                        IMPOSSIBLE,
                        "fleet_inland",
                        f"{name} cannot move to {dest.province}: a fleet moves only through seas "
                        f"and along coasts, and {dest.province} is inland",
                    )
                ]
            if self.map.is_split_coast(dest.province):
                coasts = sorted(
                    str(d)
                    for d in self.map.fleet_moves(unit.location)
                    if d.province == dest.province
                )
                if len(coasts) == 1:
                    return [
                        _note(
                            IMPOSSIBLE,
                            "wrong_coast",
                            f"{name} can reach only {coasts[0]} of {dest.province}: "
                            f"order {name} - {coasts[0]}",
                        )
                    ]
                if coasts:
                    return [
                        _note(
                            IMPOSSIBLE,
                            "name_coast",
                            f"{dest.province} has two coasts and {name} can reach both: "
                            f"name one, {_join(coasts)}",
                        )
                    ]
            return []
        # An army.
        if dest_type is ProvinceType.WATER:
            return [
                _note(
                    IMPOSSIBLE,
                    "army_to_sea",
                    f"{name} cannot move to {dest.province}: an army cannot enter a sea; "
                    f"it crosses water only when fleets convoy it",
                )
            ]
        if self.map.province_type(unit.province) is not ProvinceType.COAST:
            return [
                _note(
                    IMPOSSIBLE,
                    "inland_army",
                    f"{name} cannot reach {dest.province} this turn: {unit.province} is inland, "
                    f"so no fleet can convoy it",
                )
            ]
        if dest_type is not ProvinceType.COAST:
            return [
                _note(
                    IMPOSSIBLE,
                    "inland_destination",
                    f"{name} cannot reach {dest.province} this turn: {dest.province} is inland, "
                    f"so no fleet can convoy it there",
                )
            ]
        return []

    def _refused_support(
        self, order: SupportHold | SupportMove, unit: Unit
    ) -> list[dict[str, str]]:
        target = order.target.province if isinstance(order, SupportHold) else order.dest.province
        if target == unit.province:
            return []
        name = self.label(unit)
        exclude = {unit.province, target}
        if isinstance(order, SupportMove):
            exclude.add(order.origin.province)
        could = [
            self.label(u)
            for u in sorted(self.state.units_of(self.power), key=lambda u: u.province)
            if u.province not in exclude and _can_reach(self.map, u, target)
        ]
        text = (
            f"{name} cannot support into {target}: a unit can support only into a province "
            f"it could move to itself, and {name} cannot move to {target}"
        )
        if could:
            text += f". Your units that could give this support: {_join(could, 'and')}"
        return [_note(IMPOSSIBLE, "support_out_of_reach", text)]

    def _refused_convoy(self, order: Convoy, unit: Unit) -> list[dict[str, str]]:
        name = self.label(unit)
        if unit.kind is not UnitKind.FLEET:
            return [
                _note(
                    IMPOSSIBLE, "convoy_by_army", f"only a fleet can convoy, and {name} is an army"
                )
            ]
        if self.map.province_type(unit.province) is not ProvinceType.WATER:
            return [
                _note(
                    IMPOSSIBLE,
                    "convoy_from_coast",
                    f"{name} is in a coastal province: only a fleet at sea can convoy",
                )
            ]
        carried = self.unit(order.origin.province)
        if carried is None:
            return [
                _note(
                    IMPOSSIBLE,
                    "convoy_no_army",
                    f"there is no army in {order.origin.province} to convoy",
                )
            ]
        if carried.kind is not UnitKind.ARMY:
            return [
                _note(
                    IMPOSSIBLE,
                    "convoy_of_fleet",
                    f"{self.label(carried)} is a fleet: only an army can be convoyed",
                )
            ]
        for prov, where in ((order.origin.province, "from"), (order.dest.province, "to")):
            if self.map.province_type(prov) is not ProvinceType.COAST:
                return [
                    _note(
                        IMPOSSIBLE,
                        "convoy_inland",
                        f"{prov} is not on a coast, so no fleet can convoy an army {where} it",
                    )
                ]
        return []

    def _refused_retreat(self, order: Retreat) -> list[dict[str, str]]:
        du = self.state.dislodged_at(order.unit.province)
        if du is None or du.unit.power != self.power:
            return []
        name = self.label(du.unit)
        why = retreat_refusal(
            self.map,
            du.unit,
            order.dest,
            du.attacker_origin,
            {u.province for u in self.state.units},
            self.state.contested,
        )
        options = sorted(str(loc) for loc in du.retreats)
        if options:
            rest = f"{name} can retreat to {_join(options)}, or disband"
        else:
            rest = f"{name} has no retreat and can only disband"
        if why:
            return [
                _note(
                    IMPOSSIBLE,
                    "retreat_refused",
                    f"{name} cannot retreat to {order.dest.province}: {why}. {rest}",
                )
            ]
        return [_note(IMPOSSIBLE, "retreat_refused", rest)]

    def _refused_build(self, order: Build) -> list[dict[str, str]]:
        centers = len(self.state.centers_of(self.power))
        units = len(self.state.units_of(self.power))
        if centers <= units:
            counts = f"{_plural(centers, 'supply centre')} and {_plural(units, 'unit')}"
            if centers == units:
                return [_note(IMPOSSIBLE, "no_build_due", f"no build is due: you have {counts}")]
            return [
                _note(
                    IMPOSSIBLE,
                    "no_build_due",
                    f"no build is due: you have {counts}, so you must disband {_plural(units - centers, 'unit')}",
                )
            ]
        province = order.location.province
        builds = legal_builds(self.power, self.state, self.map)
        here = sorted(
            f"{b.kind.value} {b.location}" for b in builds if b.location.province == province
        )
        if here:
            # The site is fine; the unit type or coast is not.
            return [
                _note(IMPOSSIBLE, "build_wrong_unit", f"in {province} you can build {_join(here)}")
            ]
        if province not in self.map.home_centers.get(self.power, frozenset()):
            why = f"{province} is not one of your home supply centres"
        elif self.state.ownership.get(province) != self.power:
            why = f"you do not own {province} now"
        elif self.state.unit_at(province) is not None:
            why = f"{province} is occupied"
        else:
            why = f"{province} cannot take that unit"
        sites = sorted({f"{b.kind.value} {b.location}" for b in builds})
        if sites:
            return [
                _note(
                    IMPOSSIBLE,
                    "build_site",
                    f"you cannot build in {province}: {why}. You can build {_join(sites)}",
                )
            ]
        return [
            _note(
                IMPOSSIBLE,
                "build_site",
                f"you cannot build in {province}: {why}, and you have no free home centre of "
                f"your own to build on, so your builds are waived",
            )
        ]

    # -- accepted orders ---------------------------------------------------------

    def accepted_notes(self, order: Order) -> list[dict[str, str]]:
        if self.state.phase_type is not PhaseType.MOVEMENT:
            return []
        notes: list[dict[str, str]] = []
        if isinstance(order, Move):
            unit = self.unit(order.unit.province)
            if (
                unit is not None
                and unit.kind is UnitKind.ARMY
                and (
                    order.via_convoy
                    or not self.map.is_adjacent(unit.location, order.dest, UnitKind.ARMY)
                )
            ):
                notes.extend(self._convoy_needed(order, unit))
            notes.extend(self._same_destination(order))
        elif isinstance(order, SupportHold):
            notes.extend(self._support_hold_mismatch(order))
        elif isinstance(order, SupportMove):
            notes.extend(self._support_move_notes(order))
        elif isinstance(order, Convoy):
            notes.extend(self._convoy_notes(order))
        return notes

    def _convoy_needed(self, order: Move, unit: Unit) -> list[dict[str, str]]:
        src, dst = unit.province, order.dest.province
        shown = self.show(order)
        routes = convoy_routes(self.map, self.state, src, dst)
        if not routes:
            return [
                _note(
                    IMPOSSIBLE,
                    "no_convoy_route",
                    f"{shown} cannot succeed this turn: no chain of fleets at sea reaches from "
                    f"{src} to {dst}, so no convoy can carry it",
                )
            ]

        def ordered(fleet: Unit) -> bool:
            o = self.own.get(fleet.province)
            return (
                fleet.power == self.power
                and isinstance(o, Convoy)
                and o.origin.province == src
                and o.dest.province == dst
            )

        if any(all(ordered(f) for f in route) for route in routes):
            return []  # the player's own convoy orders already carry it
        phrases = []
        for route in routes[:_MAX_ROUTES_SHOWN]:
            names = [self.label(f) for f in route]
            if len(names) == 1:
                phrases.append(f"{names[0]} convoys it")
            elif len(names) == 2:
                phrases.append(f"{names[0]} and {names[1]} both convoy it")
            else:
                phrases.append(f"{_join(names, 'and')} all convoy it")
        text = f"{shown} needs a convoy: it can succeed only if " + ", or if ".join(phrases)
        if len(routes) > _MAX_ROUTES_SHOWN:
            text += ", or by a longer chain of fleets"
        return [_note(WARNING, "needs_convoy", text)]

    def _same_destination(self, order: Move) -> list[dict[str, str]]:
        others = [
            o
            for o in self.own.values()
            if isinstance(o, Move)
            and o.unit.province != order.unit.province
            and o.dest.province == order.dest.province
        ]
        if not others:
            return []
        names = [self.show(o) for o in sorted(others, key=lambda o: o.unit.province)]
        return [
            _note(
                WARNING,
                "same_destination",
                f"you also ordered {_join(names, 'and')}: two of your units moving into "
                f"{order.dest.province} bounce off each other unless one has more support",
            )
        ]

    def _own_order_of(self, province: str) -> tuple[Unit, Order] | None:
        """The player's own unit in ``province`` and its order (a hold if it has none)."""
        unit = self.unit(province)
        if unit is None or unit.power != self.power:
            return None
        return unit, self.own.get(province) or Hold(self.power, unit.location)

    def _doing(self, unit: Unit, theirs: Order) -> str:
        """What the player's own ``unit`` is ordered to do, as the end of a sentence."""
        if unit.province not in self.own:
            return "has no order, so it will hold"
        if isinstance(theirs, Hold):
            return "is ordered to hold"
        if isinstance(theirs, Move):
            return f"is ordered to move to {theirs.dest}"
        return f"is ordered {self.show(theirs)}"

    def _support_hold_mismatch(self, order: SupportHold) -> list[dict[str, str]]:
        found = self._own_order_of(order.target.province)
        if found is None or not isinstance(found[1], Move):
            return []
        unit, theirs = found
        return [
            _note(
                WARNING,
                "support_moving_unit",
                f"{self.label(self.unit(order.unit.province) or unit)} supports {self.label(unit)} "
                f"to hold, but {self.label(unit)} {self._doing(unit, theirs)}: a unit ordered to "
                f"move cannot be supported in place",
            )
        ]

    def _support_move_notes(self, order: SupportMove) -> list[dict[str, str]]:
        notes: list[dict[str, str]] = []
        supporter = self.unit(order.unit.province)
        found = self._own_order_of(order.origin.province)
        if found is not None and supporter is not None:
            unit, theirs = found
            if not (isinstance(theirs, Move) and theirs.dest.province == order.dest.province):
                notes.append(
                    _note(
                        WARNING,
                        "support_mismatch",
                        f"{self.label(supporter)} supports {self.label(unit)} - {order.dest.province}, "
                        f"but {self.label(unit)} {self._doing(unit, theirs)}",
                    )
                )
        there = self.unit(order.dest.province)
        if there is not None and there.power == self.power:
            notes.append(
                _note(
                    WARNING,
                    "own_unit_support",
                    own_unit_support_note(there.kind.value, there.location),
                )
            )
        return notes

    def _convoy_notes(self, order: Convoy) -> list[dict[str, str]]:
        src, dst = order.origin.province, order.dest.province
        fleet = self.unit(order.unit.province)
        if fleet is None:
            return []
        if not convoy_route_possible(self.map, self.state, src, dst, through=fleet.province):
            return [
                _note(
                    IMPOSSIBLE,
                    "convoy_off_route",
                    f"{self.label(fleet)} cannot help carry the army from {src} to {dst}: "
                    f"no chain of fleets between them passes through {fleet.province}",
                )
            ]
        found = self._own_order_of(src)
        if found is None:
            return []
        army, theirs = found
        if isinstance(theirs, Move) and theirs.dest.province == dst:
            return []
        return [
            _note(
                WARNING,
                "convoy_mismatch",
                f"{self.label(fleet)} convoys {self.label(army)} - {dst}, "
                f"but {self.label(army)} {self._doing(army, theirs)}",
            )
        ]

    # -- the set as a whole --------------------------------------------------------

    def set_notes(self, waives: int) -> list[dict[str, str]]:
        phase = self.state.phase_type
        if phase is PhaseType.MOVEMENT:
            return [
                _note(WARNING, "unordered", f"{self.label(u)} has no order, so it will hold")
                for u in sorted(self.state.units_of(self.power), key=lambda u: u.province)
                if u.province not in self.own
            ]
        if phase is PhaseType.RETREAT:
            return [
                _note(
                    WARNING,
                    "unordered",
                    f"{self.label(du.unit)} has no order, so it will be disbanded",
                )
                for du in sorted(self.state.dislodged, key=lambda du: du.province)
                if du.power == self.power and du.province not in self.own
            ]
        delta = len(self.state.centers_of(self.power)) - len(self.state.units_of(self.power))
        slots = adjustments_owed(self.map, self.state, self.power)
        if delta > 0:
            given = sum(isinstance(o, Build) for o in self.own.values()) + waives
            left = slots - given
            if left > 0:
                return [
                    _note(
                        WARNING,
                        "builds_left",
                        f"you may build {_plural(left, 'more unit')}; a build you do not order is waived",
                    )
                ]
        elif delta < 0:
            given = sum(isinstance(o, Disband) for o in self.own.values())
            left = slots - given
            if left > 0:
                return [
                    _note(
                        WARNING,
                        "disbands_left",
                        f"you must disband {_plural(left, 'more unit')}; if you do not choose, the "
                        f"units farthest from your home centres are removed for you",
                    )
                ]
        return []


def _can_reach(map: MapData, unit: Unit, province: str) -> bool:
    if unit.kind is UnitKind.ARMY:
        return province in map.army_moves(unit.province)
    return any(loc.province == province for loc in map.fleet_moves(unit.location))
