"""M3 property tests (Hypothesis): resolver invariants over random positions.

The headline property is **determinism** — the outcome must not depend on the
order in which orders are submitted. The old engine's central defect was exactly
this order-dependence, so it is the invariant most worth pinning.

Other invariants: at most one unit per province after resolution, unit
conservation (nothing is created or lost — every unit either survives or is
dislodged), and every dislodged unit has a computed (possibly empty) retreat set.
"""

from __future__ import annotations

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from engine.adjudicator.movement import adjudicate_movement
from engine.map_loader import load_standard_map
from engine.types import (
    GameState,
    Hold,
    Location,
    Move,
    PhaseType,
    ProvinceType,
    Season,
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
    """Build ``n`` armies on distinct provinces with random hold/move orders."""
    rng = random.Random(seed)
    provs = rng.sample(_ARMY_PROVS, n)
    powers = ["FRANCE", "GERMANY", "ITALY", "RUSSIA", "AUSTRIA"]
    units: list[Unit] = []
    orders: list = []
    for i, prov in enumerate(provs):
        power = powers[i % len(powers)]
        unit = Unit(UnitKind.ARMY, power, Location(prov))
        units.append(unit)
        dests = sorted(_MAP.army_moves(prov))
        if dests and rng.random() < 0.75:
            dest = rng.choice(dests)
            orders.append(Move(power, Location(prov), Location(dest)))
        else:
            orders.append(Hold(power, Location(prov)))
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
def test_dislodged_units_have_retreat_sets(seed, n):
    units, orders = _random_army_position(seed, n)
    resolution, _ = adjudicate_movement(_MAP, _state(units), list(orders))
    for r in resolution.results:
        if r.dislodged:
            # retreat_options is always a (possibly empty) tuple of Locations.
            assert isinstance(r.retreat_options, tuple)
            for loc in r.retreat_options:
                assert isinstance(loc, Location)
