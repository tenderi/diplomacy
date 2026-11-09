"""A fleet on a split coast supports from the coast it stands on.

``validate`` accepts a support order that names no coast (``F SPA S A MAR``).
The adjudicator used to compute the fleet's reach from the order's coastless
location, which has no fleet adjacencies, so the support came out VOID. The
server fills in the board's coast before storing an order, so players never hit
this, but direct engine callers did.
"""

from __future__ import annotations

from engine.adjudicator.movement import adjudicate_movement
from engine.map_loader import load_standard_map
from engine.orders.parser import parse_order
from engine.orders.validation import validate
from engine.types import (
    GameState,
    Location,
    ResultCode,
    PhaseType,
    Season,
    Unit,
    UnitKind,
)


def test_a_coastless_support_from_a_split_coast_fleet_is_valid() -> None:
    m = load_standard_map()
    state = GameState(
        year=1901,
        season=Season.SPRING,
        phase_type=PhaseType.MOVEMENT,
        units=frozenset(
            {
                Unit(UnitKind.FLEET, "FRANCE", Location("SPA", "SC")),
                Unit(UnitKind.ARMY, "FRANCE", Location("MAR")),
                Unit(UnitKind.ARMY, "ITALY", Location("PIE")),
            }
        ),
        ownership={},
    )
    support = parse_order("F SPA S A MAR", power="FRANCE", map=m)
    attack = parse_order("A PIE - MAR", power="ITALY", map=m)
    assert validate(support, state, m).ok

    resolution, new_state = adjudicate_movement(m, state, [support, attack])

    results = {r.order: r.result for r in resolution.results}
    assert results[support] is ResultCode.OK
    assert results[attack] is ResultCode.BOUNCE
    assert Unit(UnitKind.ARMY, "FRANCE", Location("MAR")) in new_state.units
