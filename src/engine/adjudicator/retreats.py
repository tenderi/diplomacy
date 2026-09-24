"""Retreat-phase adjudicator and the authoritative retreat-legality function.

The movement adjudicator records each dislodged unit as a ``DislodgedUnit`` whose
``retreats`` field is filled by :func:`compute_retreat_options` — the *single*
source of truth for where a dislodged unit may go. Legality is computed against
**post-resolution** occupancy (the board as it stands after moves apply), and
excludes:

- the province the dislodging attacker moved from (``attacker_origin``) — you
  can't retreat back the way the attacker came (``None`` when the attack was
  convoyed, which imposes no such block);
- every province a surviving unit now occupies;
- every ``contested`` province (a standoff this phase — no one may retreat in).

The retreat phase itself then resolves the submitted Retreat/Disband orders:
unordered or illegally-ordered dislodged units disband, and when two or more
units retreat to the same province **all** of them bounce and disband (rulebook:
simultaneous retreats to one province all fail).
"""

from __future__ import annotations

from typing import Optional

from engine.map_loader import MapData
from engine.types import (
    Disband,
    DislodgedUnit,
    GameState,
    Location,
    Order,
    OrderResult,
    Resolution,
    ResultCode,
    Retreat,
    Unit,
    UnitKind,
)

__all__ = ["compute_retreat_options", "adjudicate_retreats"]


def compute_retreat_options(
    map: MapData,
    unit: Unit,
    attacker_origin: Optional[str],
    occupied: frozenset[str] | set[str],
    contested: frozenset[str] | set[str],
) -> tuple[Location, ...]:
    """Legal retreat destinations for ``unit``, sorted for determinism.

    A destination is legal iff the unit could move there by land/sea adjacency,
    it is not the (non-convoyed) ``attacker_origin``, no surviving unit occupies
    it, and it did not stand off (``contested``). Coasts are first-class: a fleet
    at a split-coast province yields one entry per reachable coast.
    """
    if unit.kind is UnitKind.ARMY:
        dests: list[Location] = [Location(p) for p in map.army_moves(unit.province)]
    else:
        dests = list(map.fleet_moves(unit.location))

    opts: list[Location] = []
    for d in dests:
        if attacker_origin is not None and d.province == attacker_origin:
            continue
        if d.province in occupied:
            continue
        if d.province in contested:
            continue
        opts.append(d)
    return tuple(sorted(set(opts)))


def adjudicate_retreats(
    map: MapData, state: GameState, orders: list[Order]
) -> tuple[Resolution, GameState]:
    """Adjudicate one retreat phase.

    ``state.dislodged`` holds the units awaiting orders (with precomputed legal
    ``retreats``). Returns a per-order ``Resolution`` and the resulting
    ``GameState`` with successful retreats placed on the board and ``dislodged``/
    ``contested`` cleared.
    """
    # Index submitted orders by the province of the unit they act on.
    order_by_prov: dict[str, Order] = {}
    for o in orders:
        loc = getattr(o, "unit", None)
        if isinstance(loc, Location) and isinstance(o, (Retreat, Disband)):
            order_by_prov[loc.province] = o

    # Decide, per dislodged unit, the destination it *attempts* (None = disband).
    attempts: dict[str, tuple[DislodgedUnit, Optional[Location]]] = {}
    for du in state.dislodged:
        o = order_by_prov.get(du.province)
        dest: Optional[Location] = None
        if isinstance(o, Retreat) and _retreat_is_legal(o, du):
            dest = _canonical_dest(o.dest, du)
        attempts[du.province] = (du, dest)

    # Standoff: any province two or more units try to retreat into fails for all.
    dest_counts: dict[str, int] = {}
    for _du, dest in attempts.values():
        if dest is not None:
            dest_counts[dest.province] = dest_counts.get(dest.province, 0) + 1

    surviving: dict[str, Unit] = {u.province: u for u in state.units}
    results: list[OrderResult] = []

    for prov, (du, dest) in attempts.items():
        o = order_by_prov.get(prov)
        if dest is not None and dest_counts[dest.province] == 1:
            moved = Unit(du.kind, du.power, dest)
            surviving[dest.province] = moved
            order = o if isinstance(o, Retreat) else Retreat(du.power, du.location, dest)
            results.append(OrderResult(order=order, result=ResultCode.OK))
        else:
            # Unordered, illegal, or bounced retreat, or an explicit disband.
            order = o if isinstance(o, (Retreat, Disband)) else Disband(du.power, du.location)
            results.append(OrderResult(order=order, result=ResultCode.DISBAND))

    new_state = GameState(
        year=state.year,
        season=state.season,
        phase_type=state.phase_type,
        units=frozenset(surviving.values()),
        ownership=dict(state.ownership),
        dislodged=(),
        contested=frozenset(),
        status=state.status,
    )
    return Resolution(tuple(results)), new_state


def _retreat_is_legal(order: Retreat, du: DislodgedUnit) -> bool:
    """A Retreat is legal iff its destination is in the precomputed legal set.

    Coast handling mirrors movement: for a split-coast destination the order must
    name the coast (matched exactly); elsewhere the coast is ignored.
    """
    for legal in du.retreats:
        if legal.province != order.dest.province:
            continue
        if legal.coast is None:
            return True  # non-split destination; coast irrelevant
        if order.dest.coast == legal.coast:
            return True
    return False


def _canonical_dest(dest: Location, du: DislodgedUnit) -> Location:
    """Return the legal destination Location (coast-corrected) for ``dest``."""
    for legal in du.retreats:
        if legal.province == dest.province and (
            legal.coast is None or legal.coast == dest.coast
        ):
            return legal
    return dest
