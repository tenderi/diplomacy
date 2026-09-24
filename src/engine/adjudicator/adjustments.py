"""Adjustment-phase adjudicator — builds, disbands, waives, civil disorder.

Winter adjustments reconcile each power's **unit count** with its **supply-center
count**. For a power owning ``c`` centers and fielding ``u`` units:

- ``c > u`` — the power is entitled to build ``c - u`` units, but no more than
  the number of its **vacant, owned home** supply centers. Each ``Build`` order
  is validated (home SC, currently owned, vacant, correct coast for fleets);
  valid builds up to the entitlement are honoured, the rest are void. Unused
  entitlement — whether from explicit ``Waive`` orders or simply missing builds —
  is waived (no unit appears).
- ``c < u`` — the power must remove ``u - c`` units. Valid ``Disband`` orders are
  honoured up to that count; any shortfall is made up by **civil-disorder**
  auto-removal (rulebook §CIVIL-DISORDER REMOVALS): the unit farthest from its
  nearest home SC by shortest route (including convoys) goes first, the fleet
  before the army, ties broken by province name alphabetically.
- ``c == u`` — no adjustment; any build/disband order is void.

Everything is a pure function ``(map, state, orders) -> (Resolution, new_state)``.
"""

from __future__ import annotations

from collections import deque

from engine.map_loader import MapData
from engine.orders.validation import validate
from engine.types import (
    Build,
    Disband,
    GameState,
    Location,
    Order,
    OrderResult,
    Resolution,
    ResultCode,
    Unit,
    UnitKind,
    Waive,
)

__all__ = ["adjudicate_adjustments"]


def adjudicate_adjustments(
    map: MapData, state: GameState, orders: list[Order]
) -> tuple[Resolution, GameState]:
    """Adjudicate one adjustment (build/disband) phase."""
    results: list[OrderResult] = []
    # Units keyed by province; we add builds and drop disbands as we go.
    units_by_prov: dict[str, Unit] = {u.province: u for u in state.units}

    powers = sorted(
        {u.power for u in state.units} | set(state.ownership.values())
    )
    for power in powers:
        centers = len(state.centers_of(power))
        power_units = [u for u in state.units if u.power == power]
        delta = centers - len(power_units)
        power_orders = [o for o in orders if o.power == power]

        if delta > 0:
            results.extend(
                _resolve_builds(map, state, power, delta, power_orders, units_by_prov)
            )
        elif delta < 0:
            results.extend(
                _resolve_disbands(map, power, -delta, power_orders, units_by_prov)
            )
        else:
            # Balanced: no adjustment is allowed; any order is void.
            for o in power_orders:
                if isinstance(o, (Build, Disband, Waive)):
                    results.append(OrderResult(order=o, result=ResultCode.VOID))

    new_state = GameState(
        year=state.year,
        season=state.season,
        phase_type=state.phase_type,
        units=frozenset(units_by_prov.values()),
        ownership=dict(state.ownership),
        dislodged=(),
        contested=frozenset(),
        status=state.status,
    )
    return Resolution(tuple(results)), new_state


def _resolve_builds(
    map: MapData,
    state: GameState,
    power: str,
    entitlement: int,
    orders: list[Order],
    units_by_prov: dict[str, Unit],
) -> list[OrderResult]:
    """Honour up to ``entitlement`` valid builds; waive the remainder."""
    results: list[OrderResult] = []
    built = 0
    used_provinces: set[str] = set()

    for o in orders:
        if isinstance(o, Waive):
            if built < entitlement:
                built += 1  # an explicit waive consumes one build slot
                results.append(OrderResult(order=o, result=ResultCode.WAIVE))
            else:
                results.append(OrderResult(order=o, result=ResultCode.VOID))
            continue
        if isinstance(o, Disband):
            # A disband while entitled to build is meaningless: void.
            results.append(OrderResult(order=o, result=ResultCode.VOID))
            continue
        if not isinstance(o, Build):
            continue
        if built >= entitlement:
            results.append(OrderResult(order=o, result=ResultCode.VOID))
            continue
        if o.location.province in used_provinces:
            results.append(OrderResult(order=o, result=ResultCode.VOID))
            continue
        if not validate(o, state, map).ok:
            results.append(OrderResult(order=o, result=ResultCode.VOID))
            continue
        units_by_prov[o.location.province] = Unit(o.kind, power, o.location)
        used_provinces.add(o.location.province)
        built += 1
        results.append(OrderResult(order=o, result=ResultCode.BUILD))

    # Any unused entitlement is implicitly waived (no order, no unit).
    for _ in range(entitlement - built):
        results.append(OrderResult(order=Waive(power), result=ResultCode.WAIVE))
    return results


def _resolve_disbands(
    map: MapData,
    power: str,
    required: int,
    orders: list[Order],
    units_by_prov: dict[str, Unit],
) -> list[OrderResult]:
    """Honour up to ``required`` valid disbands; make up any shortfall by civil disorder."""
    results: list[OrderResult] = []
    disbanded: set[str] = set()

    for o in orders:
        if isinstance(o, Disband):
            unit = units_by_prov.get(o.unit.province)
            if (
                unit is None
                or unit.power != power
                or o.unit.province in disbanded
                or len(disbanded) >= required
            ):
                results.append(OrderResult(order=o, result=ResultCode.VOID))
                continue
            disbanded.add(o.unit.province)
            del units_by_prov[o.unit.province]
            results.append(OrderResult(order=o, result=ResultCode.DISBAND))
        elif isinstance(o, (Build, Waive)):
            # Can't build (or waive a build) while owing disbands: void.
            results.append(OrderResult(order=o, result=ResultCode.VOID))

    # Civil disorder: auto-remove the remaining shortfall by the distance rule.
    shortfall = required - len(disbanded)
    if shortfall > 0:
        remaining = [
            u for u in units_by_prov.values() if u.power == power
        ]
        for unit in _civil_disorder_order(map, power, remaining)[:shortfall]:
            del units_by_prov[unit.province]
            results.append(
                OrderResult(order=Disband(power, unit.location), result=ResultCode.DISBAND)
            )
    return results


def _civil_disorder_order(map: MapData, power: str, units: list[Unit]) -> list[Unit]:
    """Units in the order they are removed under civil disorder.

    Farthest from the nearest home SC first; ties: fleet before army; then
    province name alphabetically.
    """

    def key(u: Unit) -> tuple[int, int, str]:
        dist = _distance_to_home(map, power, u)
        fleet_first = 0 if u.kind is UnitKind.FLEET else 1
        return (-dist, fleet_first, u.province)

    return sorted(units, key=key)


def _distance_to_home(map: MapData, power: str, unit: Unit) -> int:
    """Shortest route (any adjacency, i.e. including convoys) to a home SC.

    Armies traverse land *and* sea steps (a convoy could carry them); fleets are
    restricted to fleet adjacency. Returns a large sentinel if home is unreachable.
    """
    homes = map.home_centers.get(power, frozenset())
    if unit.province in homes:
        return 0

    seen = {unit.province}
    if unit.kind is UnitKind.FLEET:
        queue: deque[tuple[Location, int]] = deque([(unit.location, 0)])
        while queue:
            loc, d = queue.popleft()
            for nxt in map.fleet_moves(loc):
                if nxt.province in seen:
                    continue
                if nxt.province in homes:
                    return d + 1
                seen.add(nxt.province)
                queue.append((nxt, d + 1))
    else:
        prov_queue: deque[tuple[str, int]] = deque([(unit.province, 0)])
        while prov_queue:
            prov, d = prov_queue.popleft()
            for nxt_prov in _all_neighbors(map, prov):
                if nxt_prov in seen:
                    continue
                if nxt_prov in homes:
                    return d + 1
                seen.add(nxt_prov)
                prov_queue.append((nxt_prov, d + 1))

    return 10_000  # unreachable (shouldn't happen on the standard map)


def _all_neighbors(map: MapData, province: str) -> set[str]:
    """All adjacent provinces regardless of type (land + sea) — convoy-inclusive."""
    out: set[str] = set(map.army_moves(province))
    for floc in map.fleet_locations(province):
        for nxt in map.fleet_moves(floc):
            out.add(nxt.province)
    return out
