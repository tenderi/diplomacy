"""Two processes adjudicating the same phase: exactly one wins.

Each uvicorn worker has its own ``asyncio.Lock``, so the only cross-process guard is
``GameRepo.save_state(expected_phase_code=...)``: the write is refused with
``StaleGameError`` when the persisted phase is no longer the one the caller loaded.
Every trigger -- the process-turn route, the deadline scheduler, auto-processing --
must treat that as "someone else did it" and neither report nor redo the turn.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from persistence.game_repo import StaleGameError
from server.api import app
from server.api import shared as api_shared
from server.api.shared import db_service, game_service
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

BOT = {"X-Bot-Secret": BOT_SECRET}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _game_with_an_order(client: TestClient) -> tuple[str, str]:
    tg = _telegram_user(client, "racer")
    game_id = str(client.post("/games/create", json=_as(tg, map_name="standard"), headers=BOT).json()["game_id"])
    assert client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE")).status_code == 200
    assert client.post("/games/set_orders", json=_as(tg, game_id=game_id, power="FRANCE", orders=["A PAR - BUR"])).status_code == 200
    return game_id, tg


def test_the_repo_refuses_a_write_for_a_phase_that_has_moved_on(client: TestClient) -> None:
    game_id, _ = _game_with_an_order(client)
    repo = game_service._repo
    before = repo.get_state_json(game_id)
    with pytest.raises(StaleGameError, match="expected phase 'W1905A'"):
        repo.save_state(game_id, {"clobbered": True}, phase_code="S1906M", status="active", expected_phase_code="W1905A")
    assert repo.get_state_json(game_id) == before
    assert game_service.meta(game_id)["phase_code"] == "S1901M"


def test_the_loser_of_an_interleaved_race_changes_nothing(client: TestClient) -> None:
    """Worker A loads S1901M, worker B processes it, then A tries to save its result."""
    game_id, _ = _game_with_an_order(client)
    loaded_by_a = game_service.load(game_id)
    game_service.process_turn(game_id)  # worker B
    after_b = game_service._repo.get_state_json(game_id)

    with patch.object(game_service, "load", return_value=loaded_by_a), pytest.raises(StaleGameError):
        game_service.process_turn(game_id)  # worker A, holding the stale board

    assert game_service._repo.get_state_json(game_id) == after_b
    assert game_service.meta(game_id)["phase_code"] == "F1901M"
    assert list(game_service.order_history(game_id)) == ["0"]  # one turn recorded, not two
    assert {u["location"] for u in game_service.view(game_id)["units_by_power"]["FRANCE"]} >= {"BUR"}


def test_the_route_answers_409_and_announces_nothing(client: TestClient) -> None:
    game_id, _ = _game_with_an_order(client)
    stale = StaleGameError(f"game {game_id}: already processed concurrently")
    with OutboxProbe() as probe, patch.object(game_service, "process_turn", side_effect=stale):
        resp = client.post(f"/games/{game_id}/process_turn", headers=BOT)
    assert resp.status_code == 409
    assert "already processed concurrently" in resp.json()["detail"]
    assert probe.rows() == []
    assert db_service.get_game_snapshots_by_game_id(int(db_service.get_game_by_game_id(game_id).id)) == []


def test_the_deadline_scheduler_skips_a_game_another_worker_processed(client: TestClient) -> None:
    game_id, tg = _game_with_an_order(client)
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    assert client.post(f"/games/{game_id}/deadline", json=_as(tg, deadline=past)).status_code == 200
    stale = StaleGameError("already processed concurrently")
    with OutboxProbe() as probe, patch.object(game_service, "process_turn", side_effect=stale):
        api_shared.process_due_deadlines(datetime.now(timezone.utc))
    assert not any("processed" in m.lower() for m in probe.messages())
    assert game_service.meta(game_id)["phase_code"] == "S1901M"


def test_auto_processing_stops_when_it_loses_the_race(client: TestClient) -> None:
    game_id, _ = _game_with_an_order(client)
    with patch.object(game_service, "ready_to_auto_process", return_value=True), \
         patch.object(game_service, "process_turn", side_effect=StaleGameError("lost")) as process:
        assert api_shared.maybe_auto_process(game_id) == 0
    assert process.call_count == 1  # tried once, did not spin
