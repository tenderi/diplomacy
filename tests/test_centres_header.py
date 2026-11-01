"""CD2: a centres line never sits under a results header that does not apply."""

import pytest

from server.api.shared import turn_results_lines

pytestmark = pytest.mark.unit

CENTRES = "Centres: +TRI (now 4)."


def test_centres_only_after_a_folded_retreat_phase_has_no_header() -> None:
    assert turn_results_lines("Fall 1901 retreats", {"AUSTRIA": [CENTRES]}) == [CENTRES]


def test_centres_only_for_one_of_several_powers_is_tagged_not_headed() -> None:
    lines = turn_results_lines("Fall 1901 retreats", {"AUSTRIA": [CENTRES], "ITALY": ["F NAP retreated to ROM."]})
    assert lines == [
        "As AUSTRIA: " + CENTRES,
        "As ITALY, your results for Fall 1901 retreats:",
        "F NAP retreated to ROM.",
    ]


def test_a_power_that_retreated_keeps_its_header() -> None:
    assert turn_results_lines("Fall 1901 retreats", {"ITALY": ["F NAP retreated to ROM.", CENTRES]}) == [
        "Your results for Fall 1901 retreats:",
        "F NAP retreated to ROM.",
        CENTRES,
    ]


def test_a_normal_fall_turn_keeps_centres_under_the_movement_header() -> None:
    assert turn_results_lines("Fall 1901 movement", {"AUSTRIA": ["A VIE - TRI succeeded.", CENTRES]}) == [
        "Your results for Fall 1901 movement:",
        "A VIE - TRI succeeded.",
        CENTRES,
    ]
