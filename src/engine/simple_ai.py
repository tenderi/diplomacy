"""A deliberately dumb order generator for the new engine types.

Not a real AI — a heuristic bot used for demo games and the self-play smoke test.
It produces *legal-shaped* orders for every phase (movement, retreat, adjustment);
anything it gets subtly wrong is simply voided by the adjudicator, so it can never
crash the engine. Determinism is controllable via the ``seed``.

This replaces the legacy ``strategic_ai.OrderGenerator`` (deleted in M6); it depends
only on the pure engine (``types`` + ``map_loader``) and stdlib.
"""

from __future__ import annotations

import random

from engine.map_loader import MapData
from engine.types import (
    Build,
    Disband,
    GameState,
    Hold,
    Location,
    Move,
    Order,
    PhaseType,
    Retreat,
    Unit,
    UnitKind,
)

__all__ = ["generate_orders"]


def generate_orders(
    map: MapData, state: GameState, power: str, rng: random.Random | None = None
) -> list[Order]:
    """Generate one power's orders for whatever phase ``state`` is in."""
    rng = rng or random.Random()
    if state.phase_type is PhaseType.MOVEMENT:
        return _movement_orders(map, state, power, rng)
    if state.phase_type is PhaseType.RETREAT:
        return _retreat_orders(state, power, rng)
    return _adjustment_orders(map, state, power, rng)


def _movement_orders(
    map: MapData, state: GameState, power: str, rng: random.Random
) -> list[Order]:
    orders: list[Order] = []
    for unit in sorted(state.units_of(power), key=lambda u: str(u.location)):
        dests = _reachable(map, unit)
        if dests and rng.random() < 0.6:
            dest = rng.choice(dests)
            orders.append(Move(power, unit.location, dest))
        else:
            orders.append(Hold(power, unit.location))
    return orders


def _retreat_orders(state: GameState, power: str, rng: random.Random) -> list[Order]:
    orders: list[Order] = []
    for du in state.dislodged:
        if du.power != power:
            continue
        if du.retreats:
            dest = rng.choice(sorted(du.retreats))
            orders.append(Retreat(power, du.location, dest))
        else:
            orders.append(Disband(power, du.location))
    return orders


def _adjustment_orders(
    map: MapData, state: GameState, power: str, rng: random.Random
) -> list[Order]:
    orders: list[Order] = []
    units = list(state.units_of(power))
    centers = len(state.centers_of(power))
    delta = centers - len(units)

    if delta > 0:
        # Build on vacant, owned home supply centers.
        sites = [
            p
            for p in sorted(map.home_centers.get(power, frozenset()))
            if state.ownership.get(p) == power and state.unit_at(p) is None
        ]
        rng.shuffle(sites)
        for prov in sites[:delta]:
            orders.append(_build_for(map, power, prov))
    elif delta < 0:
        # Disband a random subset; civil disorder covers any we miss.
        removable = sorted(units, key=lambda u: str(u.location))
        rng.shuffle(removable)
        for unit in removable[: -delta]:
            orders.append(Disband(power, unit.location))
    return orders


def _build_for(map: MapData, power: str, province: str) -> Build:
    """Build a coast-correct fleet on a coastal home SC, else an army."""
    ptype = map.province_type(province)
    if ptype.value == "COAST":
        coasts = map.coasts_of(province)
        coast = coasts[0] if coasts else None
        return Build(power, Location(province, coast), UnitKind.FLEET)
    return Build(power, Location(province, None), UnitKind.ARMY)


def _reachable(map: MapData, unit: Unit) -> list[Location]:
    if unit.kind is UnitKind.ARMY:
        return [Location(p) for p in sorted(map.army_moves(unit.province))]
    return sorted(map.fleet_moves(unit.location), key=str)
