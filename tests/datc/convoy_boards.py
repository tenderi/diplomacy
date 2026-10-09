"""Seeded random movement boards rich in convoys, for the resolver's property tests.

``convoy_board(seed)`` builds a cluster of sea fleets with the coasts around them,
gives some coastal armies convoyed moves along chains of those fleets (sometimes
with a spare parallel convoyer), attacks convoying fleets with supported fleet
moves (the shape of every convoy paradox), and gives everything else a random
move, support, hold or convoy order. Supports and convoys may be mismatched:
those are legal and simply do nothing. The same seed always gives the same board.
"""

from __future__ import annotations

import random

from engine.map_loader import load_standard_map
from engine.types import (
    Convoy,
    GameState,
    Hold,
    Location,
    Move,
    Order,
    PhaseType,
    ProvinceType,
    Season,
    SupportHold,
    SupportMove,
    Unit,
    UnitKind,
)

_MAP = load_standard_map()
_SEAS = sorted(p for p in _MAP.provinces if _MAP.province_type(p) is ProvinceType.WATER)
_POWERS = ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "TURKEY"]


def _fleet_touches(floc: Location, prov: str) -> bool:
    return any(d.province == prov for d in _MAP.fleet_moves(floc))


def _neighbours(prov: str) -> set[str]:
    out = set(_MAP.army_moves(prov))
    for loc in _MAP.fleet_locations(prov):
        out |= {d.province for d in _MAP.fleet_moves(loc)}
    return out


def _reach(unit: Unit) -> set[str]:
    if unit.kind is UnitKind.ARMY:
        return set(_MAP.army_moves(unit.province))
    return {d.province for d in _MAP.fleet_moves(unit.location)}


def _place_units(rng: random.Random) -> tuple[list[str], dict[str, Unit]]:
    """A cluster of 1-5 adjacent seas, each with a fleet, and units around it."""
    cluster = [rng.choice(_SEAS)]
    size = rng.choice([1, 2, 2, 3, 3, 4, 5])
    while len(cluster) < size:
        frontier = sorted(
            {
                d.province
                for p in cluster
                for d in _MAP.fleet_moves(Location(p))
                if _MAP.province_type(d.province) is ProvinceType.WATER
            }
            - set(cluster)
        )
        if not frontier:
            break
        cluster.append(rng.choice(frontier))
    region = set(cluster)
    for p in cluster:
        region |= _neighbours(p)
    if rng.random() < 0.5:
        for p in sorted(region):
            if rng.random() < 0.3:
                region |= _neighbours(p)
    powers = _POWERS[: rng.choice([2, 3, 3, 4, 5])]
    units = {p: Unit(UnitKind.FLEET, rng.choice(powers), Location(p)) for p in cluster}
    density = rng.uniform(0.3, 0.8)
    for p in sorted(region):
        if p in units or rng.random() > density:
            continue
        kind = _MAP.province_type(p)
        if kind is ProvinceType.WATER:
            units[p] = Unit(UnitKind.FLEET, rng.choice(powers), Location(p))
        elif kind is ProvinceType.LAND or rng.random() < 0.6:
            units[p] = Unit(UnitKind.ARMY, rng.choice(powers), Location(p))
        else:
            loc = rng.choice(_MAP.fleet_locations(p))
            units[p] = Unit(UnitKind.FLEET, rng.choice(powers), loc)
    return cluster, units


def _convoys(
    rng: random.Random, units: dict[str, Unit], orders: dict[str, Order], planned: dict[str, str]
) -> None:
    """Convoyed army moves along random chains of sea fleets."""
    sea_fleets = {
        p: u
        for p, u in units.items()
        if u.kind is UnitKind.FLEET and _MAP.province_type(p) is ProvinceType.WATER
    }
    armies = [
        p
        for p, u in units.items()
        if u.kind is UnitKind.ARMY
        and _MAP.province_type(p) is ProvinceType.COAST
        and any(_fleet_touches(f.location, p) for f in sea_fleets.values())
    ]
    rng.shuffle(armies)
    for army in armies[: rng.choice([0, 1, 1, 2, 2, 3])]:
        start = sorted(
            f for f, u in sea_fleets.items() if _fleet_touches(u.location, army) and f not in orders
        )
        if not start:
            continue
        path = [rng.choice(start)]
        for _ in range(rng.choice([0, 0, 1, 1, 2, 3])):
            onward = sorted(
                f
                for f, u in sea_fleets.items()
                if f not in path
                and f not in orders
                and _MAP.is_adjacent(sea_fleets[path[-1]].location, u.location, UnitKind.FLEET)
            )
            if not onward:
                break
            path.append(rng.choice(onward))
        dests = sorted(
            {
                d.province
                for d in _MAP.fleet_moves(sea_fleets[path[-1]].location)
                if _MAP.province_type(d.province) is ProvinceType.COAST and d.province != army
            }
        )
        if not dests:
            continue
        dest = rng.choice(dests)
        via = dest in _MAP.army_moves(army) and rng.random() < 0.6
        unit = units[army]
        orders[army] = Move(unit.power, unit.location, Location(dest), via_convoy=via)
        planned[army] = dest
        for f in path:
            fleet = sea_fleets[f]
            orders[f] = Convoy(fleet.power, fleet.location, Location(army), Location(dest))
        if rng.random() < 0.3:
            spare = sorted(f for f in sea_fleets if f not in orders)
            if spare:
                fleet = sea_fleets[rng.choice(spare)]
                orders[fleet.province] = Convoy(
                    fleet.power, fleet.location, Location(army), Location(dest)
                )


def _attack_convoys(
    rng: random.Random, units: dict[str, Unit], orders: dict[str, Order], planned: dict[str, str]
) -> None:
    """Supported fleet attacks on convoying fleets: the shape of a convoy paradox."""
    for target in [p for p, o in orders.items() if isinstance(o, Convoy)]:
        if rng.random() > 0.6:
            continue
        attackers = sorted(
            q
            for q in units
            if q not in orders
            and q != target
            and units[q].kind is UnitKind.FLEET
            and _fleet_touches(units[q].location, target)
        )
        if not attackers:
            continue
        q = rng.choice(attackers)
        dest = next(d for d in _MAP.fleet_moves(units[q].location) if d.province == target)
        orders[q] = Move(units[q].power, units[q].location, dest)
        planned[q] = target
        supporters = [r for r in units if r not in orders and r != q and target in _reach(units[r])]
        rng.shuffle(supporters)
        for r in supporters[: rng.choice([0, 1, 1, 2])]:
            orders[r] = SupportMove(units[r].power, units[r].location, Location(q), Location(target))


def _other_orders(
    rng: random.Random, units: dict[str, Unit], orders: dict[str, Order], planned: dict[str, str]
) -> None:
    rest = [p for p in units if p not in orders]
    rng.shuffle(rest)
    roles = {p: rng.choices(["move", "support", "hold", "convoy"], [45, 40, 10, 5])[0] for p in rest}
    for p in rest:
        unit = units[p]
        if roles[p] != "move":
            continue
        if unit.kind is UnitKind.ARMY:
            reach = [Location(d) for d in sorted(_MAP.army_moves(p))]
        else:
            reach = sorted(_MAP.fleet_moves(unit.location), key=str)
        if not reach:
            continue
        occupied = [d for d in reach if d.province in units]
        dest = rng.choice(occupied) if occupied and rng.random() < 0.7 else rng.choice(reach)
        orders[p] = Move(unit.power, unit.location, dest)
        planned[p] = dest.province
    for p in rest:
        if p in orders:
            continue
        unit = units[p]
        reach = _reach(unit)
        if roles[p] == "support":
            backable = sorted((o, d) for o, d in planned.items() if d in reach and p not in (o, d))
            holders = sorted(q for q in units if q in reach and q not in planned)
            if backable and rng.random() < 0.8:
                origin, dest = rng.choice(backable)
                orders[p] = SupportMove(unit.power, unit.location, Location(origin), Location(dest))
            elif holders:
                orders[p] = SupportHold(unit.power, unit.location, Location(rng.choice(holders)))
        elif (
            roles[p] == "convoy"
            and unit.kind is UnitKind.FLEET
            and _MAP.province_type(p) is ProvinceType.WATER
        ):
            # A random convoy, often matching no army's move.
            coasts = sorted(
                q
                for q in units
                if units[q].kind is UnitKind.ARMY
                and _MAP.province_type(q) is ProvinceType.COAST
            )
            if coasts:
                army = rng.choice(coasts)
                dests = sorted(
                    {
                        d.province
                        for d in _MAP.fleet_moves(unit.location)
                        if _MAP.province_type(d.province) is ProvinceType.COAST
                        and d.province != army
                    }
                )
                if dests:
                    orders[p] = Convoy(
                        unit.power, unit.location, Location(army), Location(rng.choice(dests))
                    )
        if p not in orders and rng.random() < 0.7:
            orders[p] = Hold(unit.power, unit.location)


def convoy_board(seed: int) -> tuple[GameState, list[Order]]:
    """The board and the orders (in a seeded random order) for ``seed``."""
    rng = random.Random(seed)
    _, units = _place_units(rng)
    orders: dict[str, Order] = {}
    planned: dict[str, str] = {}  # mover's province -> its destination province
    _convoys(rng, units, orders, planned)
    _attack_convoys(rng, units, orders, planned)
    _other_orders(rng, units, orders, planned)
    state = GameState(1901, Season.FALL, PhaseType.MOVEMENT, units=frozenset(units.values()))
    order_list = list(orders.values())
    rng.shuffle(order_list)
    return state, order_list
