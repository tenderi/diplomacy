"""DL3: the void-support explanations for fleets (split coasts included) and for a
hold-supported unit that moved, and the end-of-game lines for a game nobody won,
from boards the engine really adjudicates (no database)."""
from __future__ import annotations

import pytest

from engine.adjudicator.movement import adjudicate_movement
from engine.map_loader import load_standard_map
from engine.orders.parser import parse_order
from engine.serialization import location_from_str
from engine.types import GameState, PhaseType, Season, Unit, UnitKind
from server.api.shared import _turn_ending_texts
from server.game_service import _resolution_dict
from tests.test_result_reasons import _reasons

pytestmark = pytest.mark.unit

_MAP = load_standard_map()


def _resolve(units: dict[str, str], orders: dict[str, list[str]]) -> dict:
    """Like ``test_result_reasons._resolve``, but a fleet may name its coast."""
    board = frozenset(Unit(UnitKind(t[0]), p, location_from_str(t[2:])) for t, p in units.items())
    state = GameState(1901, Season.SPRING, PhaseType.MOVEMENT, units=board)
    parsed = [parse_order(o, power=p, map=_MAP) for p, os in orders.items() for o in os]
    resolution, _ = adjudicate_movement(_MAP, state, parsed)
    return _resolution_dict(resolution, state)


def _reason(units: dict[str, str], orders: list[str]) -> str | None:
    """The explanation attached to the first order, whose unit is the supporter."""
    by_power: dict[str, list[str]] = {}
    for text in orders:
        unit = text.split(" S ")[0].split(" - ")[0].removesuffix(" H")
        by_power.setdefault(units[unit], []).append(text)
    return _reasons(_resolve(units, by_power)).get(orders[0])


@pytest.mark.parametrize(
    ("units", "orders", "expected"),
    [
        # the coast borders the destination: the supported unit just stayed
        ({"F SPA/SC": "FRANCE", "A PIE": "FRANCE"}, ["F SPA/SC S A PIE - MAR", "A PIE H"],
         "A PIE did not move to MAR"),
        ({"F STP/SC": "RUSSIA", "A SWE": "RUSSIA"}, ["F STP/SC S A SWE - FIN", "A SWE H"],
         "A SWE did not move to FIN"),
        ({"F BUL/SC": "TURKEY", "A ALB": "TURKEY"}, ["F BUL/SC S A ALB - GRE", "A ALB H"],
         "A ALB did not move to GRE"),
        # the other coast does not border it: invalid, no explanation
        ({"F SPA/NC": "FRANCE", "A PIE": "FRANCE"}, ["F SPA/NC S A PIE - MAR", "A PIE H"], None),
        ({"F STP/NC": "RUSSIA", "A SWE": "RUSSIA"}, ["F STP/NC S A SWE - FIN", "A SWE H"], None),
        ({"F BUL/EC": "TURKEY", "A ALB": "TURKEY"}, ["F BUL/EC S A ALB - GRE", "A ALB H"], None),
        # ... but it does border its own destinations
        ({"F STP/NC": "RUSSIA", "A SWE": "RUSSIA"}, ["F STP/NC S A SWE - NWY", "A SWE H"],
         "A SWE did not move to NWY"),
        ({"F BUL/EC": "TURKEY", "A SER": "TURKEY"}, ["F BUL/EC S A SER - RUM", "A SER H"],
         "A SER did not move to RUM"),
        # an army supporter that does not border the destination
        ({"A PAR": "FRANCE", "A PIE": "FRANCE"}, ["A PAR S A PIE - MAR", "A PIE H"], None),
    ],
)
def test_void_support_move_texts_for_fleets_and_split_coasts(
    units: dict[str, str], orders: list[str], expected: str | None
) -> None:
    assert _reason(units, orders) == expected


@pytest.mark.parametrize(
    ("units", "orders", "expected"),
    [
        # the supported unit moved
        ({"F BUL/SC": "TURKEY", "A GRE": "TURKEY"}, ["F BUL/SC S A GRE", "A GRE - ALB"], "A GRE moved"),
        ({"F SPA/SC": "FRANCE", "A MAR": "FRANCE"}, ["F SPA/SC S A MAR", "A MAR - PIE"], "A MAR moved"),
        ({"F STP/SC": "RUSSIA", "A FIN": "RUSSIA"}, ["F STP/SC S A FIN", "A FIN - SWE"], "A FIN moved"),
        # it was ordered to move but failed
        (
            {"F BUL/SC": "TURKEY", "A GRE": "TURKEY", "A SER": "AUSTRIA", "A BUD": "AUSTRIA"},
            ["F BUL/SC S A GRE", "A GRE - ALB", "A SER - ALB", "A BUD H"],
            "A GRE was ordered to move",
        ),
        # the supporter's coast does not border the unit: invalid
        ({"F BUL/EC": "TURKEY", "A GRE": "TURKEY"}, ["F BUL/EC S A GRE", "A GRE - ALB"], None),
        ({"F SPA/NC": "FRANCE", "A MAR": "FRANCE"}, ["F SPA/NC S A MAR", "A MAR - PIE"], None),
        ({"F STP/NC": "RUSSIA", "A FIN": "RUSSIA"}, ["F STP/NC S A FIN", "A FIN - SWE"], None),
    ],
)
def test_void_support_hold_texts_say_the_supported_unit_moved(
    units: dict[str, str], orders: list[str], expected: str | None
) -> None:
    assert _reason(units, orders) == expected


def test_end_of_game_texts_for_a_game_nobody_won() -> None:
    assert _turn_ending_texts("7", [], "no_winner") == ("Game 7 has ended: no power is left, so nobody wins", "")
    assert _turn_ending_texts("7", [], "only_dummies") == (
        "Game 7 has ended: only civil-disorder powers are left, so nobody wins",
        "",
    )
