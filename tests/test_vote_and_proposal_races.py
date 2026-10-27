"""Draw votes, concessions and deadline proposals under races (BU2).

Each test drives one guard through the route a client calls and pins the exact
status and detail: a turn processed while a draw vote or a concession was in
flight (``StaleGameError`` -> 409, the game still active), the game row gone
between the route's existence check and the service's load (404), a power that
is out voting or conceding again (409), and a power that is out proposing or
voting on a deadline change (400). ``tests/test_concurrency_guards.py`` covers
the game that *ended* meanwhile.

The races are simulated the way ``test_concurrency_guards`` does it: the request
is handed the board from before the other write (``GameService.load``), and the
other write really happens, so the refusal comes from the repository's own
locked phase check, not from a patched exception.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from server.api.shared import game_service
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies
from tests.test_concurrent_processing import BOT
from tests.test_quit_and_replace import _as, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _game(client: TestClient, *powers: str) -> tuple[str, dict[str, str]]:
    """A started game with ``powers`` seated (one Telegram user each) and the
    rest dummies. Returns ``(game_id, {power: telegram_id})``."""
    seats = {p: _telegram_user(client, p.lower()) for p in powers}
    creator = seats[powers[0]]
    game_id = str(client.post("/games/create", json=_as(creator, map_name="standard"), headers=BOT).json()["game_id"])
    for power, tg in seats.items():
        assert client.post(f"/games/{game_id}/join", json=_as(tg, power=power)).status_code == 200
    fill_with_dummies(game_id)
    return game_id, seats


def _load_stale_first(game_id: str) -> Callable[[str], Any]:
    """``GameService.load`` that hands the request the board as it is now (the
    caller then changes it, as another request would), and the real one after."""
    stale = game_service.load(game_id)
    real_load = game_service.load
    calls = {"n": 0}

    def load(gid: str) -> Any:
        calls["n"] += 1
        return stale if calls["n"] == 1 else real_load(gid)

    return load


def _units(game_id: str, power: str) -> list[str]:
    return sorted(str(u.location.province) for u in game_service.load(game_id).state.units if u.power == power)


# -- draw votes ---------------------------------------------------------------


def test_a_draw_vote_cast_while_the_turn_was_processed_is_409_and_not_recorded(client: TestClient) -> None:
    game_id, seats = _game(client, "FRANCE", "GERMANY")
    load = _load_stale_first(game_id)
    game_service.process_turn(game_id)  # another worker: S1901M -> F1901M
    with patch.object(game_service, "load", side_effect=load):
        resp = client.post(f"/games/{game_id}/draw_vote", json=_as(seats["FRANCE"], power="FRANCE", vote=True))
    assert resp.status_code == 409
    assert resp.json()["detail"] == f"game {game_id} has moved on from S1901M to F1901M"
    assert game_service._repo.get_draw_votes(game_id) == {}
    assert game_service.meta(game_id)["status"] == "active"


def test_a_deciding_vote_whose_draw_loses_to_a_processed_turn_is_409_and_the_game_plays_on(
    client: TestClient,
) -> None:
    """FRANCE is the only voter, so its yes is quorum; before the draw is
    written the turn is processed, and the draw (of S1901M's board) is refused."""
    game_id, seats = _game(client, "FRANCE")
    repo = game_service._repo
    real_modify = repo.modify_draw_votes

    def vote_then_the_turn_is_processed(*args: Any, **kwargs: Any) -> Any:
        votes = real_modify(*args, **kwargs)
        game_service.process_turn(game_id)
        return votes

    with patch.object(repo, "modify_draw_votes", side_effect=vote_then_the_turn_is_processed):
        resp = client.post(f"/games/{game_id}/draw_vote", json=_as(seats["FRANCE"], power="FRANCE", vote=True))
    assert resp.status_code == 409
    assert resp.json()["detail"] == (
        f"game {game_id}: expected phase 'S1901M' but the persisted phase is 'F1901M' -- already processed concurrently"
    )
    after = game_service.load(game_id).state
    assert after.status.value == "ACTIVE"
    assert after.phase_name == "F1901M"
    assert game_service.meta(game_id)["status"] == "active"


def test_a_draw_vote_on_a_game_deleted_meanwhile_is_404(client: TestClient) -> None:
    game_id, seats = _game(client, "FRANCE", "GERMANY")
    with patch.object(game_service, "load", return_value=None):
        resp = client.post(f"/games/{game_id}/draw_vote", json=_as(seats["FRANCE"], power="FRANCE", vote=True))
    assert resp.status_code == 404
    assert resp.json()["detail"] == f"game {game_id} not found"


def test_a_power_that_conceded_cannot_vote_on_a_draw(client: TestClient) -> None:
    game_id, seats = _game(client, "FRANCE", "GERMANY")
    assert client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE")).status_code == 200
    resp = client.post(f"/games/{game_id}/draw_vote", json=_as(seats["FRANCE"], power="FRANCE", vote=True))
    assert resp.status_code == 409
    assert resp.json()["detail"] == f"FRANCE has been eliminated from game {game_id}; it cannot vote on a draw"
    assert game_service._repo.get_draw_votes(game_id) == {}


# -- concessions ----------------------------------------------------------------


def test_a_concession_while_the_turn_was_processed_is_409_and_the_power_stays(client: TestClient) -> None:
    game_id, seats = _game(client, "FRANCE", "GERMANY")
    load = _load_stale_first(game_id)
    game_service.process_turn(game_id)
    with patch.object(game_service, "load", side_effect=load):
        resp = client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE"))
    assert resp.status_code == 409
    assert resp.json()["detail"] == f"game {game_id} has moved on from S1901M to F1901M"
    assert _units(game_id, "FRANCE") == ["BRE", "MAR", "PAR"]
    assert "FRANCE" not in game_service.load(game_id).eliminated_powers()


def test_conceding_twice_is_409(client: TestClient) -> None:
    game_id, seats = _game(client, "FRANCE", "GERMANY")
    assert client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE")).status_code == 200
    resp = client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE"))
    assert resp.status_code == 409
    assert resp.json()["detail"] == "FRANCE has already conceded"


def test_the_same_power_conceding_twice_at_once_is_409_for_the_second(client: TestClient) -> None:
    """Both requests loaded the board with FRANCE on it; the second finds the
    locked row already without FRANCE."""
    game_id, seats = _game(client, "FRANCE", "GERMANY")
    load = _load_stale_first(game_id)
    assert client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE")).status_code == 200
    with patch.object(game_service, "load", side_effect=load):
        resp = client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE"))
    assert resp.status_code == 409
    assert resp.json()["detail"] == "FRANCE has already conceded"
    assert _units(game_id, "FRANCE") == []
    assert _units(game_id, "GERMANY") == ["BER", "KIE", "MUN"]


def test_a_concession_on_a_game_deleted_meanwhile_is_404(client: TestClient) -> None:
    game_id, seats = _game(client, "FRANCE", "GERMANY")
    with patch.object(game_service, "load", return_value=None):
        resp = client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE"))
    assert resp.status_code == 404
    assert resp.json()["detail"] == f"game {game_id} not found"


# -- deadline proposals -----------------------------------------------------------


def test_a_power_that_conceded_cannot_propose_a_deadline(client: TestClient) -> None:
    game_id, seats = _game(client, "FRANCE", "GERMANY")
    assert client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE")).status_code == 200
    resp = client.post(f"/games/{game_id}/deadline/propose", json=_as(seats["FRANCE"], power="FRANCE", hours=24.0))
    assert resp.status_code == 400
    assert resp.json()["detail"] == f"FRANCE is not an active power in game {game_id}"
    assert client.get(f"/games/{game_id}/deadline").json()["pending_proposal"] is None


def test_a_power_that_conceded_cannot_vote_on_a_deadline_proposal(client: TestClient) -> None:
    game_id, seats = _game(client, "FRANCE", "GERMANY", "ITALY")
    proposed = client.post(f"/games/{game_id}/deadline/propose", json=_as(seats["GERMANY"], power="GERMANY", hours=24.0))
    assert proposed.status_code == 200
    assert proposed.json()["status"] == "pending"
    assert client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE")).status_code == 200
    resp = client.post(f"/games/{game_id}/deadline/vote", json=_as(seats["FRANCE"], power="FRANCE", vote=True))
    assert resp.status_code == 400
    assert resp.json()["detail"] == f"FRANCE is not an active power in game {game_id}"
    pending = client.get(f"/games/{game_id}/deadline").json()["pending_proposal"]
    assert pending["yes_votes"] == ["GERMANY"]


@pytest.mark.parametrize("route, body", [
    ("propose", {"hours": 24.0}),
    ("vote", {"vote": True}),
])
def test_a_deadline_write_on_a_game_deleted_meanwhile_is_400(client: TestClient, route: str, body: dict) -> None:
    game_id, seats = _game(client, "FRANCE", "GERMANY")
    with patch.object(game_service, "active_powers", return_value=None):
        resp = client.post(f"/games/{game_id}/deadline/{route}", json=_as(seats["FRANCE"], power="FRANCE", **body))
    assert resp.status_code == 400
    assert resp.json()["detail"] == f"game {game_id} not found"


def test_the_only_active_power_s_proposal_is_accepted_on_the_spot(client: TestClient) -> None:
    """FRANCE is the one power with a player (the rest are dummies, who do not
    vote), so its own yes is the majority."""
    game_id, seats = _game(client, "FRANCE")
    before = datetime.now(timezone.utc)
    resp = client.post(f"/games/{game_id}/deadline/propose", json=_as(seats["FRANCE"], power="FRANCE", hours=24.0))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["yes_votes"] == ["FRANCE"]
    assert body["needed_for_majority"] == 1
    deadline = datetime.fromisoformat(body["deadline"])
    assert before + timedelta(hours=24) <= deadline <= datetime.now(timezone.utc) + timedelta(hours=24)
    after = client.get(f"/games/{game_id}/deadline").json()
    assert after["pending_proposal"] is None
    stored = datetime.fromisoformat(after["deadline"]).replace(tzinfo=timezone.utc)
    assert abs(stored - deadline) < timedelta(seconds=1)


def test_a_vote_with_no_active_powers_decides_nothing() -> None:
    """With nobody active there is no majority to reach or to miss: undecided,
    not "rejected" by the arithmetic of a zero-sized table."""
    assert api_shared._deadline_vote_outcome({"FRANCE": "yes"}, frozenset()) is None
    assert api_shared._deadline_vote_outcome({}, frozenset()) is None
