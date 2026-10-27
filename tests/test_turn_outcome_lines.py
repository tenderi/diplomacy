"""BW1: the wording of ``GameService.turn_outcomes`` for each kind of result,
from stored resolutions (no database)."""
from __future__ import annotations

from typing import Any

import pytest

from server.game_service import GameService

pytestmark = pytest.mark.unit


class _Repo:
    def __init__(self, resolution: dict[str, Any]) -> None:
        self._resolution = resolution

    def get_resolution_history(self, _game_id: str) -> dict[str, dict[str, Any]]:
        return {"3": self._resolution}


def _r(order_str: str, order: dict[str, Any], result: str = "OK", **extra: Any) -> dict[str, Any]:
    return {"order": order, "order_str": order_str, "result": result, "dislodged": False, "retreat_options": [], **extra}


def _outcomes(*results: dict[str, Any], **stored: Any) -> dict[str, list[str]]:
    return GameService(_Repo({"results": list(results), **stored})).turn_outcomes("1", 3)


def test_movement_codes() -> None:
    out = _outcomes(
        _r("A LON - BEL VIA", {"type": "MOVE", "power": "ENGLAND", "unit": "LON", "dest": "BEL"}, "NO_CONVOY"),
        _r("F NTH C A LON - BEL", {"type": "CONVOY", "power": "ENGLAND", "unit": "NTH"}, "DISLODGED", dislodged=True),
        _r("F NWG - NTH", {"type": "MOVE", "power": "GERMANY", "unit": "NWG", "dest": "NTH"}),
        _r("A MUN S A KIE - BER", {"type": "SUPPORT_MOVE", "power": "GERMANY", "unit": "MUN"}, "CUT"),
        _r("A KIE - BUR", {"type": "MOVE", "power": "GERMANY", "unit": "KIE", "dest": "BUR"}, "VOID"),
        _r("A BUR H", {"type": "HOLD", "power": "FRANCE", "unit": "BUR"}, "DISLODGED", dislodged=True),
    )
    assert out == {
        "ENGLAND": ["A LON - BEL VIA failed: no convoy route.", "F NTH C A LON - BEL failed; dislodged by F NWG (GERMANY)."],
        "GERMANY": ["A KIE - BUR was invalid, so the unit held.", "A MUN S A KIE - BER was cut.", "F NWG - NTH succeeded."],
        # No successful move into BUR is stored: the attacker is left unnamed.
        "FRANCE": ["A BUR was dislodged."],
    }


def test_a_single_unordered_unit_keeps_its_own_line_and_centres_close_the_list() -> None:
    out = _outcomes(
        _r("A PAR H", {"type": "HOLD", "power": "FRANCE", "unit": "PAR"}, unordered=True),
        centres={"FRANCE": {"gained": [], "lost": ["BRE"], "count": 4}},
    )
    assert out == {"FRANCE": ["A PAR held (no order).", "Centres: -BRE (now 4)."]}


def test_retreat_and_adjustment_codes() -> None:
    out = _outcomes(
        _r("A BUR R PAR", {"type": "RETREAT", "power": "FRANCE", "unit": "BUR", "dest": "PAR"}, "DISBAND"),
        _r("A MAR R PIE", {"type": "RETREAT", "power": "FRANCE", "unit": "MAR", "dest": "PIE"}, "BOUNCE"),
        _r("D A WAR", {"type": "DISBAND", "power": "RUSSIA", "unit": "WAR"}, "DISBAND", unordered=True),
        _r("D A MOS", {"type": "DISBAND", "power": "RUSSIA", "unit": "MOS"}, "DISBAND", civil_disorder=True),
        _r("BUILD F STP/SC", {"type": "BUILD", "power": "RUSSIA", "location": "STP/SC", "kind": "F"}, "BUILD"),
        _r("WAIVE", {"type": "WAIVE", "power": "RUSSIA"}, "WAIVE"),
    )
    assert out == {
        "FRANCE": ["A BUR R PAR was invalid, so A BUR was disbanded."],
        "RUSSIA": ["F STP/SC was built."],
    }


def test_an_unknown_turn_has_no_outcomes() -> None:
    assert GameService(_Repo({})).turn_outcomes("1", 7) == {}


def test_a_player_holding_two_powers_gets_a_block_per_power() -> None:
    from server.api.shared import turn_results_lines

    assert turn_results_lines(
        "Fall 1901 movement", {"AUSTRIA": ["A VIE held."], "ITALY": ["A ROM - VEN bounced.", "Centres: -VEN (now 2)."]}
    ) == [
        "As AUSTRIA, your results for Fall 1901 movement:",
        "A VIE held.",
        "As ITALY, your results for Fall 1901 movement:",
        "A ROM - VEN bounced.",
        "Centres: -VEN (now 2).",
    ]
