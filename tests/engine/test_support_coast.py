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


def _spring(*units: Unit) -> GameState:
    return GameState(
        year=1901,
        season=Season.SPRING,
        phase_type=PhaseType.MOVEMENT,
        units=frozenset(units),
        ownership={},
    )


def test_a_support_naming_another_coast_does_not_match_a_coastless_move() -> None:
    """``F GAS - SPA`` goes to SPA/NC, the only coast Gascony reaches (6.B.2), so a
    support naming SPA/SC supports a move nobody made: void (6.B.9), 1 v 1."""
    m = load_standard_map()
    state = _spring(
        Unit(UnitKind.FLEET, "FRANCE", Location("GAS")),
        Unit(UnitKind.ARMY, "FRANCE", Location("MAR")),
        Unit(UnitKind.FLEET, "ENGLAND", Location("MAO")),
    )
    move = parse_order("F GAS - SPA", power="FRANCE", map=m)
    support = parse_order("A MAR S F GAS - SPA/SC", power="FRANCE", map=m)
    rival = parse_order("F MAO - SPA/NC", power="ENGLAND", map=m)
    for o in (move, support, rival):
        assert validate(o, state, m).ok

    resolution, new_state = adjudicate_movement(m, state, [move, support, rival])

    results = {r.order: r.result for r in resolution.results}
    assert results[support] is ResultCode.VOID
    assert results[move] is ResultCode.BOUNCE
    assert results[rival] is ResultCode.BOUNCE
    assert new_state.units == state.units


def test_a_support_naming_another_coast_does_not_match_black_sea_to_bulgaria() -> None:
    """``F BLA - BUL`` goes to BUL/EC; a support naming BUL/SC is void."""
    m = load_standard_map()
    state = _spring(
        Unit(UnitKind.FLEET, "RUSSIA", Location("BLA")),
        Unit(UnitKind.ARMY, "RUSSIA", Location("RUM")),
        Unit(UnitKind.FLEET, "TURKEY", Location("CON")),
    )
    move = parse_order("F BLA - BUL", power="RUSSIA", map=m)
    support = parse_order("A RUM S F BLA - BUL/SC", power="RUSSIA", map=m)
    rival = parse_order("F CON - BUL/EC", power="TURKEY", map=m)
    for o in (move, support, rival):
        assert validate(o, state, m).ok

    resolution, new_state = adjudicate_movement(m, state, [move, support, rival])

    results = {r.order: r.result for r in resolution.results}
    assert results[support] is ResultCode.VOID
    assert results[move] is ResultCode.BOUNCE
    assert results[rival] is ResultCode.BOUNCE
    assert new_state.units == state.units


def test_a_support_naming_the_reached_coast_matches_a_coastless_move() -> None:
    """The coast the support names is the one the move reaches: it counts."""
    m = load_standard_map()
    state = _spring(
        Unit(UnitKind.FLEET, "FRANCE", Location("GAS")),
        Unit(UnitKind.ARMY, "FRANCE", Location("MAR")),
        Unit(UnitKind.FLEET, "ENGLAND", Location("MAO")),
    )
    move = parse_order("F GAS - SPA", power="FRANCE", map=m)
    support = parse_order("A MAR S F GAS - SPA/NC", power="FRANCE", map=m)
    rival = parse_order("F MAO - SPA/NC", power="ENGLAND", map=m)

    resolution, new_state = adjudicate_movement(m, state, [move, support, rival])

    results = {r.order: r.result for r in resolution.results}
    assert results[support] is ResultCode.OK
    assert results[move] is ResultCode.OK
    assert Unit(UnitKind.FLEET, "FRANCE", Location("SPA", "NC")) in new_state.units
