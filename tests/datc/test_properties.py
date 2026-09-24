"""M3 property tests (Hypothesis): resolver invariants over random positions.

The headline property is **determinism** — the outcome must not depend on the
order in which orders are submitted. The old engine's central defect was exactly
this order-dependence, so it is the invariant most worth pinning.

Other invariants: at most one unit per province after resolution, unit
conservation (nothing is created or lost — every unit either survives or is
dislodged), and every retreat offered to a dislodged unit is one the rules allow.
"""

from __future__ import annotations

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from engine.adjudicator.movement import adjudicate_movement
from engine.adjudicator.retreats import adjudicate_retreats
from engine.map_loader import load_standard_map
from engine.types import (
    GameState,
    Hold,
    Location,
    Move,
    PhaseType,
    ProvinceType,
    Retreat,
    Season,
    SupportHold,
    SupportMove,
    Unit,
    UnitKind,
)

pytestmark = [pytest.mark.datc, pytest.mark.slow]

_MAP = load_standard_map()
# Land/coast provinces can host armies; use them as a stable, index-able pool.
_ARMY_PROVS = sorted(
    p for p in _MAP.provinces if _MAP.province_type(p) is not ProvinceType.WATER
)


def _random_army_position(seed: int, n: int) -> tuple[list[Unit], list]:
    """``n`` armies on a connected cluster of provinces (so they interact), each
    given a random hold, move, support-hold or support-move order. Supports are
    geometrically possible but need not match what the supported unit does --
    a mismatched support is legal and simply doesn't count."""
    rng = random.Random(seed)
    cluster = [rng.choice(_ARMY_PROVS)]
    while len(cluster) < n:
        frontier = sorted({d for p in cluster for d in _MAP.army_moves(p)} - set(cluster))
        if not frontier:
            break
        cluster.append(rng.choice(frontier))
    powers = ["FRANCE", "GERMANY", "ITALY", "RUSSIA", "AUSTRIA"]
    owner = {prov: powers[rng.randrange(len(powers))] for prov in cluster}
    units = [Unit(UnitKind.ARMY, owner[prov], Location(prov)) for prov in cluster]
    role = {prov: rng.choices(["move", "support", "hold"], weights=[45, 40, 15])[0] for prov in cluster}
    moves: dict[str, str] = {}
    for prov in cluster:
        reach = sorted(_MAP.army_moves(prov))
        if role[prov] == "move" and reach:
            attacks = [p for p in reach if p in owner]
            moves[prov] = rng.choice(attacks) if attacks and rng.random() < 0.7 else rng.choice(reach)
    orders: list = []
    for prov in cluster:
        power, here, reach = owner[prov], Location(prov), _MAP.army_moves(prov)
        if prov in moves:
            orders.append(Move(power, here, Location(moves[prov])))
        elif role[prov] == "support":
            backable = [(o, d) for o, d in moves.items() if d in reach and d != prov and o != prov]
            holders = sorted(p for p in cluster if p in reach and p not in moves)
            if backable and rng.random() < 0.8:
                origin, dest = rng.choice(sorted(backable))
                orders.append(SupportMove(power, here, Location(origin), Location(dest)))
            elif holders:
                orders.append(SupportHold(power, here, Location(rng.choice(holders))))
            else:
                orders.append(Hold(power, here))
        else:
            orders.append(Hold(power, here))
    return units, orders


def _state(units: list[Unit]) -> GameState:
    return GameState(1901, Season.SPRING, PhaseType.MOVEMENT, units=frozenset(units))


def _result_key(resolution):
    """Order-independent signature of a resolution: per-unit (code, dislodged)."""
    out = set()
    for r in resolution.results:
        loc = getattr(r.order, "unit", None) or getattr(r.order, "location", None)
        out.add((str(loc), r.result.name, r.dislodged))
    return frozenset(out)


@settings(max_examples=200, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10_000), n=st.integers(min_value=2, max_value=8))
def test_determinism_under_order_shuffling(seed, n):
    units, orders = _random_army_position(seed, n)
    state = _state(units)

    res_a, _ = adjudicate_movement(_MAP, state, list(orders))
    shuffled = list(orders)
    random.Random(seed + 1).shuffle(shuffled)
    res_b, _ = adjudicate_movement(_MAP, state, shuffled)

    assert _result_key(res_a) == _result_key(res_b)


@settings(max_examples=200, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10_000), n=st.integers(min_value=2, max_value=8))
def test_at_most_one_unit_per_province(seed, n):
    units, orders = _random_army_position(seed, n)
    _, new_state = adjudicate_movement(_MAP, _state(units), list(orders))
    provinces = [u.province for u in new_state.units]
    assert len(provinces) == len(set(provinces))


@settings(max_examples=200, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10_000), n=st.integers(min_value=2, max_value=8))
def test_unit_conservation(seed, n):
    units, orders = _random_army_position(seed, n)
    _, new_state = adjudicate_movement(_MAP, _state(units), list(orders))
    # No movement-phase unit is created or destroyed: every one either survives
    # on the board or is dislodged awaiting retreat.
    assert len(new_state.units) + len(new_state.dislodged) == len(units)


@settings(max_examples=200, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10_000), n=st.integers(min_value=2, max_value=8))
def test_retreat_options_obey_the_retreat_rules(seed, n):
    """Every offered retreat is adjacent, empty after the moves, not a standoff
    province, and not where the attacker came from; the resolution and the
    state's dislodged record offer the same set."""
    units, orders = _random_army_position(seed, n)
    resolution, new_state = adjudicate_movement(_MAP, _state(units), list(orders))
    occupied = {u.province for u in new_state.units}
    by_province = {d.unit.province: d for d in new_state.dislodged}
    dislodged_results = [r for r in resolution.results if r.dislodged]
    assert len(dislodged_results) == len(by_province)
    for r in dislodged_results:
        record = by_province[r.order.unit.province]
        assert set(r.retreat_options) == set(record.retreats)
        for loc in record.retreats:
            assert loc.province in _MAP.army_moves(record.unit.province)
            assert loc.province not in occupied
            assert loc.province not in new_state.contested
            assert loc.province != record.attacker_origin


@settings(max_examples=200, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10_000), n=st.integers(min_value=2, max_value=8))
def test_retreat_options_are_legal(seed, n):
    """Every computed retreat destination is adjacent, empty (post-move),
    uncontested, and not the (non-convoyed) attacker's origin."""
    units, orders = _random_army_position(seed, n)
    _, new_state = adjudicate_movement(_MAP, _state(units), list(orders))
    occupied = {u.province for u in new_state.units}
    for du in new_state.dislodged:
        for loc in du.retreats:
            assert loc.province in _MAP.army_moves(du.province)
            assert loc.province not in occupied
            assert loc.province not in new_state.contested
            assert loc.province != du.attacker_origin


@settings(max_examples=200, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10_000), n=st.integers(min_value=2, max_value=8))
def test_retreat_phase_leaves_a_consistent_board(seed, n):
    """After resolving retreats (each unit to its first legal option), the board
    holds at most one unit per province and no dislodged units remain."""
    units, orders = _random_army_position(seed, n)
    _, mstate = adjudicate_movement(_MAP, _state(units), list(orders))
    retreat_orders: list = []
    for du in mstate.dislodged:
        if du.retreats:
            dest = sorted(du.retreats)[0]
            retreat_orders.append(Retreat(du.power, du.location, dest))
    _, rstate = adjudicate_retreats(_MAP, mstate, retreat_orders)
    provinces = [u.province for u in rstate.units]
    assert len(provinces) == len(set(provinces))
    assert rstate.dislodged == ()
