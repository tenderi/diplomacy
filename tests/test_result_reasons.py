"""CA4: a support void for the supporter's own unit and a convoy broken by a
dislodged fleet say so, in the turn DM's lines and in ``/last_resolution``'s
``reason``, from boards the engine really adjudicates (no database)."""
from __future__ import annotations

from typing import Any

import pytest

from engine.adjudicator.movement import adjudicate_movement
from engine.map_loader import load_standard_map
from engine.orders.parser import parse_order
from engine.types import GameState, Location, PhaseType, Season, Unit, UnitKind
from server.game_service import GameService, _decorated_results, _resolution_dict, own_unit_support_note

pytestmark = pytest.mark.unit

_MAP = load_standard_map()


def _resolve(units: dict[str, str], orders: dict[str, list[str]]) -> dict[str, Any]:
    """Adjudicate ``orders`` on a board of ``units`` ({"A VIE": "AUSTRIA"})."""
    board = frozenset(
        Unit(UnitKind(text[0]), power, Location(text[2:])) for text, power in units.items()
    )
    state = GameState(1901, Season.SPRING, PhaseType.MOVEMENT, units=board)
    parsed = [parse_order(o, power=p, map=_MAP) for p, os in orders.items() for o in os]
    resolution, _ = adjudicate_movement(_MAP, state, parsed)
    return _resolution_dict(resolution, state)


class _Repo:
    def __init__(self, resolution: dict[str, Any]) -> None:
        self._resolution = resolution

    def get_resolution_history(self, _game_id: str) -> dict[str, dict[str, Any]]:
        return {"1": self._resolution}


def _outcomes(resolution: dict[str, Any]) -> dict[str, list[str]]:
    return GameService(_Repo(resolution)).turn_outcomes("1", 1)


def _reasons(resolution: dict[str, Any]) -> dict[str, str]:
    return {r["order_str"]: r["reason"] for r in _decorated_results(resolution) if "reason" in r}


def test_a_support_onto_the_supporters_own_unit_says_it_had_no_effect() -> None:
    res = _resolve(
        {"A VEN": "ITALY", "A VIE": "AUSTRIA", "F TRI": "AUSTRIA"},
        {"ITALY": ["A VEN - TRI"], "AUSTRIA": ["A VIE S A VEN - TRI", "F TRI H"]},
    )
    assert [r["result"] for r in res["results"] if r["order"]["type"] == "SUPPORT_MOVE"] == ["VOID"]
    assert _outcomes(res)["AUSTRIA"] == [
        "F TRI held.",
        "A VIE S A VEN - TRI had no effect: it would dislodge your own F TRI.",
    ]
    assert _reasons(res) == {"A VIE S A VEN - TRI": "it would dislodge your own F TRI"}


def test_a_support_of_a_move_that_was_not_ordered_keeps_the_invalid_wording() -> None:
    res = _resolve(
        {"A VEN": "ITALY", "A VIE": "AUSTRIA", "F TRI": "AUSTRIA"},
        {"ITALY": ["A VEN H"], "AUSTRIA": ["A VIE S A VEN - TRI", "F TRI H"]},
    )
    assert "A VIE S A VEN - TRI was invalid, so the unit held." in _outcomes(res)["AUSTRIA"]
    assert _reasons(res) == {}


def test_a_convoy_broken_by_a_dislodged_fleet_names_the_fleet() -> None:
    res = _resolve(
        {"A LON": "ENGLAND", "F NTH": "ENGLAND", "F SKA": "GERMANY", "F HEL": "GERMANY"},
        {"ENGLAND": ["A LON - NWY VIA", "F NTH C A LON - NWY"], "GERMANY": ["F SKA - NTH", "F HEL S F SKA - NTH"]},
    )
    assert _outcomes(res)["ENGLAND"] == [
        "A LON - NWY VIA failed: the convoy was broken when F NTH was dislodged.",
        "F NTH C A LON - NWY failed; dislodged by F SKA (GERMANY).",
    ]
    assert _reasons(res) == {"A LON - NWY VIA": "F NTH was dislodged"}


def test_a_surviving_fleet_of_a_broken_chain_names_the_lost_fleet() -> None:
    res = _resolve(
        {"A LON": "ENGLAND", "F ENG": "ENGLAND", "F MAO": "ENGLAND", "F BRE": "FRANCE", "F IRI": "FRANCE"},
        {
            "ENGLAND": ["A LON - POR VIA", "F ENG C A LON - POR", "F MAO C A LON - POR"],
            "FRANCE": ["F BRE - MAO", "F IRI S F BRE - MAO"],
        },
    )
    assert _reasons(res) == {
        "A LON - POR VIA": "F MAO was dislodged",
        "F ENG C A LON - POR": "F MAO was dislodged",
    }


def test_a_dislodged_fleet_off_the_route_is_not_blamed() -> None:
    # F MAO cannot carry A LON to NWY: its convoy is VOID, and its dislodgement
    # did not break anything.
    res = _resolve(
        {"A LON": "ENGLAND", "F NTH": "ENGLAND", "F MAO": "ENGLAND", "F BRE": "FRANCE", "F GAS": "FRANCE"},
        {
            "ENGLAND": ["A LON - NWY VIA", "F MAO C A LON - NWY", "F NTH H"],
            "FRANCE": ["F BRE - MAO", "F GAS S F BRE - MAO"],
        },
    )
    assert "A LON - NWY VIA failed: no convoy route." in _outcomes(res)["ENGLAND"]
    assert _reasons(res) == {}


def test_a_convoy_with_no_fleet_ordered_keeps_no_convoy_route() -> None:
    res = _resolve({"A LON": "ENGLAND", "F NTH": "ENGLAND"}, {"ENGLAND": ["A LON - NWY VIA", "F NTH H"]})
    assert "A LON - NWY VIA failed: no convoy route." in _outcomes(res)["ENGLAND"]
    assert _reasons(res) == {}


def test_own_unit_support_note_names_the_unit() -> None:
    assert own_unit_support_note("F", Location("TRI")) == (
        "your own F TRI is there: this support has no effect unless it moves away"
    )
