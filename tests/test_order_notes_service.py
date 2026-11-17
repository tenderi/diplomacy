"""``GameService`` wiring of the order helper notes (#460), over an in-memory repo.

The rule under test: notes come from the board and the requesting power's own
orders only, so another power's pending orders never show in them.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

import pytest

from engine.map_loader import load_standard_map
from engine.serialization import state_to_dict
from engine.types import GameState, Location, PhaseType, Season, Unit, UnitKind
from server.game_service import GameService

pytestmark = pytest.mark.unit

_MAP = load_standard_map()


class _Repo:
    """Just enough of ``GameRepo`` for ``submit_orders`` and ``order_notes``."""

    def __init__(self, state: GameState, pending: dict[str, list[str]]) -> None:
        self.state_json = state_to_dict(state)
        self.pending = pending

    def get_state_json(self, _game_id: str) -> dict[str, Any]:
        return self.state_json

    def get_pending_orders(self, _game_id: str) -> dict[str, list[str]]:
        return {p: list(o) for p, o in self.pending.items()}

    def modify_pending_orders(
        self,
        _game_id: str,
        change: Callable[[dict[str, list[str]]], dict[str, list[str]]],
        *,
        expected_phase_code: Optional[str] = None,
    ) -> dict[str, list[str]]:
        self.pending = change(self.get_pending_orders(_game_id))
        return self.pending


def _board() -> GameState:
    units = {
        Unit(UnitKind.ARMY, "ENGLAND", Location("LON")),
        Unit(UnitKind.FLEET, "ENGLAND", Location("EDI")),
        Unit(UnitKind.FLEET, "FRANCE", Location("ENG")),
        Unit(UnitKind.ARMY, "FRANCE", Location("PIC")),
    }
    return GameState(
        year=1901,
        season=Season.SPRING,
        phase_type=PhaseType.MOVEMENT,
        units=frozenset(units),
        ownership=dict(_MAP.initial_ownership),
    )


FRENCH_SECRET = ["F ENG C A LON - BEL", "A PIC - BEL"]


def _service(pending: dict[str, list[str]]) -> tuple[GameService, _Repo]:
    repo = _Repo(_board(), pending)
    return GameService(repo, _MAP), repo


def test_another_powers_pending_orders_never_reach_the_notes() -> None:
    with_french, _ = _service({"FRANCE": list(FRENCH_SECRET), "ENGLAND": ["A LON - BEL"]})
    without, _ = _service({"ENGLAND": ["A LON - BEL"]})
    for orders, merge in ((None, False), (["F EDI H"], True), (["A LON - BEL"], False)):
        seen = with_french.order_notes("1", "england", orders, merge=merge)
        assert seen == without.order_notes("1", "england", orders, merge=merge)
        text = repr(seen)
        assert "PIC" not in text and "C A LON" not in text
    assert with_french.order_notes("1", "ENGLAND")["orders"][0]["notes"][0]["text"] == (
        "A LON - BEL needs a convoy: it can succeed only if France's F ENG convoys it"
    )


def test_submit_orders_attaches_notes_from_the_stored_set_only() -> None:
    svc, repo = _service({"FRANCE": list(FRENCH_SECRET)})
    results = svc.submit_orders("1", "ENGLAND", ["A LON - BEL", "F EDI - LVP"], merge=True)
    convoy = "A LON - BEL needs a convoy: it can succeed only if France's F ENG convoys it"
    assert results[0]["note"] == convoy
    assert results[0]["notes"] == [{"kind": "warning", "code": "needs_convoy", "text": convoy}]
    assert results[1]["ok"] is False
    assert results[1]["notes"] == []  # EDI and LVP do not border: the reason says it all
    assert repo.pending["FRANCE"] == FRENCH_SECRET
    assert "needs_convoy" not in results[0]  # the internal flag does not leak out


def test_a_refused_order_is_explained() -> None:
    svc, _ = _service({})
    results = svc.submit_orders("1", "ENGLAND", ["F EDI - YOR", "A LON - NTH"])
    assert results[1]["ok"] is False
    assert results[1]["notes"] == [
        {
            "kind": "impossible",
            "code": "army_to_sea",
            "text": "A LON cannot move to NTH: an army cannot enter a sea; it crosses water only when fleets convoy it",
        }
    ]


def test_a_merged_pick_replaces_the_stored_order_for_that_unit() -> None:
    svc, _ = _service({"ENGLAND": ["A LON H", "F EDI H"]})
    out = svc.order_notes("1", "ENGLAND", ["A LON - YOR"], merge=True)
    assert [e["order"] for e in out["orders"]] == ["F EDI H", "A LON - YOR"]
    assert out["notes"] == []
    alone = svc.order_notes("1", "ENGLAND", ["A LON - YOR"])
    assert alone["notes"] == [{"kind": "warning", "code": "unordered", "text": "F EDI has no order, so it will hold"}]


def test_sandbox_results_carry_notes_too() -> None:
    svc, _ = _service({})
    checks, _parsed = svc.sandbox_orders(_board(), {"ENGLAND": ["A LON - BEL"], "FRANCE": ["F ENG C A LON - BEL"]})
    assert checks["ENGLAND"][0]["note"] == (
        "A LON - BEL needs a convoy: it can succeed only if France's F ENG convoys it"
    )
    assert checks["FRANCE"][0]["notes"] == []
