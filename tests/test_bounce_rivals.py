"""CR1: a bounced move says who it bounced against, in the turn DM and the web's
result entries (stored resolutions, no database)."""
from __future__ import annotations

from typing import Any

import pytest

from server.game_service import GameService, _decorated_results

pytestmark = pytest.mark.unit


class _Repo:
    def __init__(self, resolution: dict[str, Any]) -> None:
        self._resolution = resolution

    def get_resolution_history(self, _game_id: str) -> dict[str, dict[str, Any]]:
        return {"3": self._resolution}


def _r(order_str: str, order: dict[str, Any], result: str = "OK") -> dict[str, Any]:
    return {"order": order, "order_str": order_str, "result": result, "dislodged": False, "retreat_options": []}


def _mv(text: str, power: str, unit: str, dest: str, result: str = "BOUNCE") -> dict[str, Any]:
    return _r(text, {"type": "MOVE", "power": power, "unit": unit, "dest": dest}, result)


def _hold(text: str, power: str, unit: str) -> dict[str, Any]:
    return _r(text, {"type": "HOLD", "power": power, "unit": unit})


def _outcomes(*results: dict[str, Any]) -> dict[str, list[str]]:
    return GameService(_Repo({"results": list(results)})).turn_outcomes("1", 3)


def test_a_bounce_names_the_units_that_also_moved_there() -> None:
    out = _outcomes(
        _mv("A VIE - GAL", "AUSTRIA", "VIE", "GAL"),
        _mv("A WAR - GAL", "RUSSIA", "WAR", "GAL"),
    )
    assert out["AUSTRIA"] == ["A VIE - GAL bounced (RUSSIA's A WAR also moved there)."]
    assert out["RUSSIA"] == ["A WAR - GAL bounced (AUSTRIA's A VIE also moved there)."]


def test_three_way_bounce_lists_both_rivals() -> None:
    out = _outcomes(
        _mv("A VIE - GAL", "AUSTRIA", "VIE", "GAL"),
        _mv("A WAR - GAL", "RUSSIA", "WAR", "GAL"),
        _mv("A UKR - GAL", "RUSSIA", "UKR", "GAL"),
    )
    assert out["AUSTRIA"] == ["A VIE - GAL bounced (RUSSIA's A WAR and RUSSIA's A UKR also moved there)."]


def test_a_bounce_names_the_unit_that_kept_the_destination() -> None:
    out = _outcomes(
        _mv("A VIE - GAL", "AUSTRIA", "VIE", "GAL"),
        _hold("A GAL H", "RUSSIA", "GAL"),
    )
    assert out["AUSTRIA"] == ["A VIE - GAL bounced off RUSSIA's A GAL."]


def test_a_head_to_head_bounce_names_the_unit_it_met() -> None:
    out = _outcomes(_mv("A VIE - GAL", "AUSTRIA", "VIE", "GAL"), _mv("A GAL - VIE", "RUSSIA", "GAL", "VIE"))
    assert out["AUSTRIA"] == ["A VIE - GAL bounced off RUSSIA's A GAL."]


def test_a_lone_bounce_with_no_rival_in_the_results_stays_plain() -> None:
    assert _outcomes(_mv("A VIE - GAL", "AUSTRIA", "VIE", "GAL"))["AUSTRIA"] == ["A VIE - GAL bounced."]


def test_a_dislodged_holder_is_not_what_the_mover_bounced_off() -> None:
    results = (
        _mv("A VIE - GAL", "AUSTRIA", "VIE", "GAL"),
        {**_hold("A GAL H", "RUSSIA", "GAL"), "result": "DISLODGED", "dislodged": True},
        _mv("A RUM - GAL", "TURKEY", "RUM", "GAL", "OK"),
    )
    assert _outcomes(*results)["AUSTRIA"] == ["A VIE - GAL bounced (TURKEY's A RUM also moved there)."]
    entry = _decorated_results({"results": list(results)})[0]
    assert entry["bounced_with"] == ["TURKEY's A RUM"]
    assert "bounced_off" not in entry


def test_a_holder_whose_support_was_cut_still_counts() -> None:
    cut = _r("A GAL S A UKR - SEV", {"type": "SUPPORT_MOVE", "power": "RUSSIA", "unit": "GAL"}, "CUT")
    assert _outcomes(_mv("A VIE - GAL", "AUSTRIA", "VIE", "GAL"), cut)["AUSTRIA"] == [
        "A VIE - GAL bounced off RUSSIA's A GAL."
    ]


def test_decorated_results_carry_the_rivals_for_the_web() -> None:
    res = _decorated_results(
        {"results": [_mv("A VIE - GAL", "AUSTRIA", "VIE", "GAL"), _hold("A GAL H", "RUSSIA", "GAL")]}
    )
    assert res[0]["bounced_off"] == "RUSSIA's A GAL"
    assert "bounced_with" not in res[0]
    res = _decorated_results(
        {"results": [_mv("A VIE - GAL", "AUSTRIA", "VIE", "GAL"), _mv("A WAR - GAL", "RUSSIA", "WAR", "GAL")]}
    )
    assert res[0]["bounced_with"] == ["RUSSIA's A WAR"]
    assert "bounced_off" not in res[0]
