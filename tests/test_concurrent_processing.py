"""Two processes adjudicating the same phase: exactly one wins.

Each uvicorn worker has its own ``asyncio.Lock``, so the only cross-process guard is
``GameRepo.save_state(expected_phase_code=...)``: the write is refused with
``StaleGameError`` when the persisted phase is no longer the one the caller loaded.
Every trigger -- the process-turn route, the deadline scheduler, auto-processing --
must treat that as "someone else did it" and neither report nor redo the turn.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from persistence.database import GameModel
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
    loaded_by_a = game_service._repo.get_state_json(game_id)
    game_service.process_turn(game_id)  # worker B
    after_b = game_service._repo.get_state_json(game_id)

    with patch.object(game_service._repo, "get_state_json", return_value=loaded_by_a), pytest.raises(StaleGameError):
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


def test_the_phase_check_and_the_write_are_one_step(client: TestClient) -> None:
    """The check read ``phase_code`` with a plain SELECT. Another worker's
    transaction that had not committed yet was invisible to it, so both workers
    passed the check and the second write clobbered the first. Here a second
    transaction holds the row and moves the phase on while the writer checks:
    the writer must wait for it and then refuse, not write over it."""
    game_id, _ = _game_with_an_order(client)
    repo = game_service._repo
    other = repo._session_factory()
    row = other.query(GameModel).filter_by(game_id=game_id).with_for_update().one()

    outcome: dict = {}

    def writer() -> None:
        try:
            repo.save_state(game_id, {"clobbered": True}, phase_code="F1901M", status="active", expected_phase_code="S1901M")
            outcome["result"] = "wrote"
        except StaleGameError:
            outcome["result"] = "stale"

    thread = threading.Thread(target=writer)
    thread.start()
    time.sleep(0.5)  # the writer is now waiting on the row
    row.phase_code = "F1901M"
    row.state_json = {"winner": True}
    other.commit()
    other.close()
    thread.join(timeout=10)
    assert outcome == {"result": "stale"}
    assert repo.get_state_json(game_id) == {"winner": True}


def test_a_concession_from_a_phase_that_has_moved_on_is_refused(client: TestClient) -> None:
    """``concede`` wrote its whole board unguarded: computed from S1901M and
    written after a concurrent turn reached F1901M, it rolled the game back."""
    game_id, tg = _game_with_an_order(client)
    stale = game_service.load(game_id)
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    with patch.object(game_service, "load", return_value=stale):
        resp = client.post(f"/games/{game_id}/concede", json=_as(tg, power="FRANCE"))
    assert resp.status_code == 409
    assert game_service.meta(game_id)["phase_code"] == "F1901M"


def test_two_players_ordering_at_once_both_keep_their_orders(client: TestClient) -> None:
    """``submit_orders`` read ``pending_orders`` in one transaction and wrote the
    whole dict back in another. Here GERMANY's submission commits while
    FRANCE's is in flight: FRANCE's write must build on it, not erase it."""
    game_id, _ = _game_with_an_order(client)
    repo = game_service._repo
    other = repo._session_factory()
    row = other.query(GameModel).filter_by(game_id=game_id).with_for_update().one()

    thread = threading.Thread(target=lambda: game_service.submit_orders(game_id, "FRANCE", ["A MAR H"], merge=True))
    thread.start()
    time.sleep(0.5)  # FRANCE's submission is now waiting on the row
    row.pending_orders = {**dict(row.pending_orders), "GERMANY": ["A MUN H"]}
    other.commit()
    other.close()
    thread.join(timeout=10)
    assert game_service._repo.get_pending_orders(game_id) == {"FRANCE": ["A PAR - BUR", "A MAR H"], "GERMANY": ["A MUN H"]}


def test_orders_checked_against_a_processed_phase_are_refused(client: TestClient) -> None:
    """Validated against S1901M, written after the turn reached F1901M: the old
    code stored them as F1901M orders (a hold is legal there too)."""
    game_id, tg = _game_with_an_order(client)
    stale = game_service.load(game_id)
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    with patch.object(game_service, "load", return_value=stale):
        resp = client.post("/games/set_orders", json=_as(tg, game_id=game_id, power="FRANCE", orders=["A MAR H"]))
    assert resp.status_code == 409 and "none were applied" in resp.json()["detail"]
    assert game_service._repo.get_pending_orders(game_id) == {}


def test_an_order_arriving_mid_adjudication_is_adjudicated_not_dropped(client: TestClient) -> None:
    """``process_turn`` read the orders, adjudicated, then cleared them in a
    separate write: an order accepted in between was wiped without ever being
    adjudicated. Now the write refuses and the turn is adjudicated again."""
    game_id, _ = _game_with_an_order(client)
    repo = game_service._repo
    real_read = repo.get_pending_orders
    calls = {"n": 0}

    def read_then_someone_orders(gid: str) -> dict:
        seen = real_read(gid)
        calls["n"] += 1
        if calls["n"] == 1:  # GERMANY's order lands after this read
            game_service.submit_orders(game_id, "GERMANY", ["A MUN - BOH"])
        return seen

    with patch.object(repo, "get_pending_orders", side_effect=read_then_someone_orders):
        result = game_service.process_turn(game_id)
    ordered = {r["order_str"] for r in result["resolution"]["results"]}
    assert {"A PAR - BUR", "A MUN - BOH"} <= ordered
    assert "BOH" in {u["location"] for u in game_service.view(game_id)["units_by_power"]["GERMANY"]}
    assert repo.get_pending_orders(game_id) == {}


def test_two_wait_flags_raised_at_once_both_hold(client: TestClient) -> None:
    """``set_wait`` read the flags, added its own and wrote them back: GERMANY's
    flag committed meanwhile was erased, and the turn could auto-process past a
    player who had asked it to wait."""
    game_id, _ = _game_with_an_order(client)
    repo = game_service._repo
    other = repo._session_factory()
    row = other.query(GameModel).filter_by(game_id=game_id).with_for_update().one()

    thread = threading.Thread(target=lambda: game_service.set_wait(game_id, "FRANCE", True))
    thread.start()
    time.sleep(0.5)
    row.wait_flags = {"GERMANY": True}
    other.commit()
    other.close()
    thread.join(timeout=10)
    assert game_service.wait_flags(game_id) == frozenset({"FRANCE", "GERMANY"})
