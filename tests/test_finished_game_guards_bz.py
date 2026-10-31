"""Track BZ: what a finished game still does (BZ2, BZ3, BZ5).

A finished game cannot be taken over (BZ2), holds no pending deadline proposal
(BZ3), shows no open draw vote unless a draw ended it (BZ3), and still carries
post-mortem press (BZ5, deliberate).
"""
from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from engine.serialization import state_to_dict
from engine.types import GameStatus
from persistence.database_service import DeadlineProposalChange
from server.api import app
from server.api.shared import db_service, game_service
from tests.conftest import _get_db_url
from tests.test_concurrency_guards import _end_in_a_draw
from tests.test_concurrent_processing import _game_with_an_order
from tests.test_quit_and_replace import _as, _game_with_france, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

PROPOSAL = {
    "proposed_by": "FRANCE",
    "value_hours": 24.0,
    "votes": {"FRANCE": "yes"},
    "vote_deadline": None,
    "created_at": "2026-01-01T00:00:00+00:00",
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _seed_proposal(game_id: str) -> None:
    db_service.modify_deadline_proposal(game_id, lambda _cur: DeadlineProposalChange(PROPOSAL, {}))


def test_replacing_into_a_finished_game_is_409(client: TestClient) -> None:
    game_id, tg = _game_with_an_order(client)
    assert client.post(f"/games/{game_id}/quit", json=_as(tg)).status_code == 200
    _end_in_a_draw(game_id)
    late = _telegram_user(client, "latereplacer")
    resp = client.post(f"/games/{game_id}/replace", json=_as(late, power="FRANCE"))
    assert resp.status_code == 409
    assert resp.json()["detail"] == f"Game {game_id} has ended; it cannot be joined."
    seat = next(p for p in client.get(f"/games/{game_id}/players").json() if p["power"] == "FRANCE")
    assert seat["user_id"] is None


def test_a_finished_game_reports_no_pending_deadline_proposal(client: TestClient) -> None:
    game_id, _ = _game_with_an_order(client)
    _seed_proposal(game_id)
    assert client.get(f"/games/{game_id}/deadline").json()["pending_proposal"]["proposed_by"] == "FRANCE"
    _end_in_a_draw(game_id)
    assert client.get(f"/games/{game_id}/deadline").json()["pending_proposal"] is None


def test_withdrawing_a_proposal_on_a_finished_game_is_409(client: TestClient) -> None:
    game_id, tg = _game_with_an_order(client)
    _seed_proposal(game_id)
    _end_in_a_draw(game_id)
    resp = client.post(f"/games/{game_id}/deadline/withdraw", json=_as(tg, power="FRANCE"))
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Game is over; its deadline can no longer be changed."


def test_a_game_not_ended_by_a_draw_shows_no_open_draw_vote(client: TestClient) -> None:
    game_id, _ = _game_with_an_order(client)
    state = game_service.load(game_id).state
    won = replace(state, status=GameStatus.COMPLETED, winners=frozenset({"FRANCE"}))
    game_service._repo.save_state(game_id, state_to_dict(won), phase_code=won.phase_name, status="completed")
    body = client.get(f"/games/{game_id}/draw_vote_status").json()
    assert (body["required"], body["votes"], body["missing"], body["quorum_reached"]) == ([], [], [], False)
    assert body["game_status"] == "COMPLETED"


def test_press_is_still_accepted_after_the_game_ends(client: TestClient) -> None:
    """Post-mortem chat is deliberate (BZ5): press is the one write a finished game takes."""
    game_id, tg = _game_with_france(client)
    other = _telegram_user(client, "postmortem")
    assert client.post(f"/games/{game_id}/join", json=_as(other, power="GERMANY")).status_code == 200
    _end_in_a_draw(game_id)
    r = client.post(f"/games/{game_id}/message", json=_as(tg, recipient_power="GERMANY", text="gg"))
    assert r.status_code == 200, r.text
    r = client.post(f"/games/{game_id}/broadcast", json=_as(tg, text="well played"))
    assert r.status_code == 200, r.text


def test_replacing_into_a_dummy_seat_is_409(client: TestClient) -> None:
    """BZ6: a vacated seat the creator made a dummy is not takeable by /replace, as by /join."""
    game_id, tg = _game_with_france(client)
    other = _telegram_user(client, "keeper")
    assert client.post(f"/games/{game_id}/join", json=_as(other, power="GERMANY")).status_code == 200
    assert client.post(f"/games/{game_id}/quit", json=_as(tg)).status_code == 200
    assert "FRANCE" in game_service.set_dummy(game_id, "FRANCE", True)["dummy_powers"]
    late = _telegram_user(client, "dummytaker")
    resp = client.post(f"/games/{game_id}/replace", json=_as(late, power="FRANCE"))
    assert resp.status_code == 409
    assert resp.json()["detail"] == f"FRANCE is played by civil disorder in game {game_id}; the game's creator can open it."
    seat = next(p for p in client.get(f"/games/{game_id}/players").json() if p["power"] == "FRANCE")
    assert seat["user_id"] is None
