"""One validation path for orders, shared by server, adjudicator precheck, everything.

``validate`` checks structural/topological legality of a single order against
a ``GameState`` and a ``MapData`` — it does not know about the other orders
submitted in the same phase (that's the adjudicator's job: cutting support,
resolving standoffs, matching convoy chains). It answers questions like "does
a unit belonging to this power actually stand here", "is the destination
reachable", "is the coast valid" — the kind of thing that is wrong no matter
what everyone else orders this phase.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.map_loader import MapData
from engine.types import (
    Build,
    Convoy,
    Disband,
    GameState,
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

__all__ = ["ValidationResult", "validate"]


@dataclass(frozen=True)
class ValidationResult:
    """The outcome of validating one order: ``ok`` plus an optional reason."""

    ok: bool
    reason: str | None = None


def _find_unit(loc: Location, pool: frozenset[Unit]) -> Unit | None:
    for unit in pool:
        if unit.province == loc.province:
            return unit
    return None


def _can_reach_province(map: MapData, frm: Location, kind: UnitKind, dest_province: str) -> bool:
    """Whether a unit of ``kind`` at ``frm`` could move to (any coast of) ``dest_province``.

    Used for support range, which ignores the supported unit's specific coast.
    """
    if kind is UnitKind.ARMY:
        return dest_province in map.army_moves(frm.province)
    return any(loc.province == dest_province for loc in map.fleet_moves(frm))


def validate(order: Order, state: GameState, map: MapData) -> ValidationResult:
    """Validate ``order`` against the current ``state`` and ``map`` topology."""
    if isinstance(order, Waive):
        return ValidationResult(True)

    if isinstance(order, Build):
        return _validate_build(order, state, map)

    if isinstance(order, Retreat):
        unit = _find_unit(order.unit, state.dislodged)
        if unit is None:
            return ValidationResult(False, f"no dislodged unit at {order.unit.province}")
        ownership_error = _check_ownership(order, unit)
        if ownership_error is not None:
            return ownership_error
        return _validate_retreat(order, unit, map)

    if isinstance(order, Disband):
        pool = state.dislodged if state.phase_type is PhaseType.RETREAT else state.units
        unit = _find_unit(order.unit, pool)
        if unit is None:
            return ValidationResult(False, f"no unit to disband at {order.unit.province}")
        ownership_error = _check_ownership(order, unit)
        if ownership_error is not None:
            return ownership_error
        return ValidationResult(True)

    # Hold / Move / SupportHold / SupportMove / Convoy: an on-board unit.
    unit = state.unit_at(order.unit.province)
    if unit is None:
        return ValidationResult(False, f"no unit at {order.unit.province}")
    ownership_error = _check_ownership(order, unit)
    if ownership_error is not None:
        return ownership_error
    if order.unit.coast is not None and unit.location.coast != order.unit.coast:
        return ValidationResult(
            False,
            f"unit at {order.unit.province} is on coast {unit.location.coast!r}, "
            f"not {order.unit.coast!r}",
        )

    if isinstance(order, Hold):
        return ValidationResult(True)
    if isinstance(order, Move):
        return _validate_move(order, unit, map)
    if isinstance(order, SupportHold):
        return _validate_support_hold(order, unit, map)
    if isinstance(order, SupportMove):
        return _validate_support_move(order, unit, map)
    if isinstance(order, Convoy):
        return _validate_convoy(order, unit, map)

    return ValidationResult(False, f"unsupported order type: {order.order_type}")


def _check_ownership(order: Order, unit: Unit) -> ValidationResult | None:
    if unit.power != order.power:
        return ValidationResult(
            False, f"unit at {unit.province} belongs to {unit.power}, not {order.power}"
        )
    return None


def _validate_move(order: Move, unit: Unit, map: MapData) -> ValidationResult:
    dest = order.dest
    kind = unit.kind

    if order.via_convoy:
        if kind is not UnitKind.ARMY:
            return ValidationResult(False, "only an army may move via convoy")
        if map.province_type(unit.location.province) is not ProvinceType.COAST:
            return ValidationResult(
                False, f"{unit.location.province} is not coastal (required to embark a convoy)"
            )
        if map.province_type(dest.province) is not ProvinceType.COAST:
            return ValidationResult(
                False, f"{dest.province} is not coastal (required to disembark a convoy)"
            )
        return ValidationResult(True)

    if kind is UnitKind.FLEET and map.is_split_coast(dest.province) and dest.coast is None:
        return ValidationResult(
            False, f"fleet move into split-coast {dest.province} must name a coast"
        )
    if not map.is_adjacent(unit.location, dest, kind):
        return ValidationResult(False, f"{dest} is not adjacent to {unit.location}")
    return ValidationResult(True)


def _validate_support_hold(order: SupportHold, unit: Unit, map: MapData) -> ValidationResult:
    if order.target.province == unit.location.province:
        return ValidationResult(False, "a unit cannot support itself")
    if not _can_reach_province(map, unit.location, unit.kind, order.target.province):
        return ValidationResult(
            False, f"{unit.location} cannot reach {order.target.province} to support"
        )
    return ValidationResult(True)


def _validate_support_move(order: SupportMove, unit: Unit, map: MapData) -> ValidationResult:
    if not _can_reach_province(map, unit.location, unit.kind, order.dest.province):
        return ValidationResult(
            False, f"{unit.location} cannot reach {order.dest.province} to support a move"
        )
    return ValidationResult(True)


def _validate_convoy(order: Convoy, unit: Unit, map: MapData) -> ValidationResult:
    if unit.kind is not UnitKind.FLEET:
        return ValidationResult(False, "only a fleet may convoy")
    if map.province_type(unit.location.province) is not ProvinceType.WATER:
        return ValidationResult(False, "a convoying fleet must be in a sea space")
    if map.province_type(order.origin.province) is not ProvinceType.COAST:
        return ValidationResult(False, f"{order.origin.province} is not a coastal province")
    if map.province_type(order.dest.province) is not ProvinceType.COAST:
        return ValidationResult(False, f"{order.dest.province} is not a coastal province")
    return ValidationResult(True)


def _validate_retreat(order: Retreat, unit: Unit, map: MapData) -> ValidationResult:
    dest = order.dest
    if not map.is_adjacent(unit.location, dest, unit.kind):
        return ValidationResult(False, f"{dest} is not adjacent to {unit.location}")
    if unit.kind is UnitKind.FLEET and map.is_split_coast(dest.province) and dest.coast is None:
        return ValidationResult(
            False, f"fleet retreat into split-coast {dest.province} must name a coast"
        )
    return ValidationResult(True)


def _validate_build(order: Build, state: GameState, map: MapData) -> ValidationResult:
    loc = order.location
    province = loc.province

    if province not in map.home_centers.get(order.power, frozenset()):
        return ValidationResult(False, f"{province} is not a home supply center of {order.power}")
    if state.ownership.get(province) != order.power:
        return ValidationResult(False, f"{province} is not currently owned by {order.power}")
    if state.unit_at(province) is not None:
        return ValidationResult(False, f"{province} is occupied")

    ptype = map.province_type(province)
    if order.kind is UnitKind.FLEET:
        if ptype is ProvinceType.LAND:
            return ValidationResult(False, f"cannot build a fleet on landlocked {province}")
        if map.is_split_coast(province):
            if loc.coast is None or loc.coast not in map.coasts_of(province):
                return ValidationResult(
                    False, f"fleet build at split-coast {province} must name a valid coast"
                )
        elif loc.coast is not None:
            return ValidationResult(False, f"{province} has no coasts to choose from")
    else:
        if ptype is ProvinceType.WATER:
            return ValidationResult(False, f"cannot build an army at sea: {province}")
        if loc.coast is not None:
            return ValidationResult(False, "an army build may not specify a coast")

    return ValidationResult(True)
