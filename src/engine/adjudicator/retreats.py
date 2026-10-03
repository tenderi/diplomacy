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

__all__ = ["compute_retreat_options", "retreat_refusal", "adjudicate_retreats"]


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

    opts = [
        d for d in dests if _blocked_reason(d.province, attacker_origin, occupied, contested) is None
    ]
    return tuple(sorted(set(opts)))


def retreat_refusal(
    map: MapData,
    unit: Unit,
    dest: Location,
    attacker_origin: Optional[str],
    occupied: frozenset[str] | set[str],
    contested: frozenset[str] | set[str],
) -> Optional[str]:
    """Why ``unit`` may not retreat to ``dest``, or ``None`` if nothing forbids it.

    The same rules as :func:`compute_retreat_options`, phrased for a player: the
    destination is out of reach, it is where the attacker came from, a unit now
    stands there, or a standoff left it empty this turn. A fleet's ``dest``
    without a coast counts as reachable when any coast of it is.
    """
    if unit.kind is UnitKind.ARMY:
        reachable = dest.province in map.army_moves(unit.province)
    elif dest.coast is None:
        reachable = any(d.province == dest.province for d in map.fleet_moves(unit.location))
    else:
        reachable = dest in map.fleet_moves(unit.location)
    if not reachable:
        return f"it is not adjacent to {unit.location}"
    return _blocked_reason(dest.province, attacker_origin, occupied, contested)


def _blocked_reason(
    province: str,
    attacker_origin: Optional[str],
    occupied: frozenset[str] | set[str],
    contested: frozenset[str] | set[str],
) -> Optional[str]:
    """The retreat-only exclusions for a reachable ``province`` (``None``: open)."""
    if attacker_origin is not None and province == attacker_origin:
        return "the unit that dislodged it attacked from there"
    if province in occupied:
        return "another unit stands there"
    if province in contested:
        return "a standoff left it empty this turn, and no unit may retreat there"
    return None


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
        if isinstance(o, Retreat):
            dest = _legal_dest(o, du)
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


def _legal_dest(order: Retreat, du: DislodgedUnit) -> Optional[Location]:
    """The legal destination ``order`` names (coast-corrected), or ``None``.

    Coast handling mirrors movement: a split-coast destination named with a
    coast must match that coast exactly; named without one, it is the sole
    legal coast when there is exactly one, and illegal (ambiguous) otherwise.
    Elsewhere the coast is irrelevant.
    """
    matches = [legal for legal in du.retreats if legal.province == order.dest.province]
    for legal in matches:
        if legal.coast is None or legal.coast == order.dest.coast:
            return legal
    if order.dest.coast is None and len(matches) == 1:
        return matches[0]
    return None
