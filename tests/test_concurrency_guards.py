"""Concurrency and write guards that no other test reaches (BH3).

Each test drives one guard through the route a client calls and pins the exact
status and message: the per-game process-turn lock, a game that finished while a
draw vote or a concession was in flight, adjudication retries running out, and
joining a finished game. ``tests/test_idempotency_middleware.py`` covers the
idempotency guards.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from engine.serialization import state_to_dict
from persistence.game_repo import PhaseInputsChangedError
from server.api import app
from server.api.shared import game_service
from server.game_service import _ADJUDICATION_ATTEMPTS
from tests.conftest import _get_db_url
from tests.test_concurrent_processing import BOT, _game_with_an_order
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

ALL_DRAWN = "drawn between AUSTRIA, ENGLAND, FRANCE, GERMANY, ITALY, RUSSIA, TURKEY"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _end_in_a_draw(game_id: str) -> None:
    """Another request finishes the game: a draw among every power on the board."""
    drawn = game_service.load(game_id).draw()
    game_service._repo.save_state(
        game_id, state_to_dict(drawn.state), phase_code=drawn.state.phase_name, status="completed"
    )


def _load_active_first(game_id: str) -> Callable[[str], Any]:
    """``GameService.load`` that hands the request the board from before the game
    ended (as if the draw landed just after its read), then the real one."""
    stale = game_service.load(game_id)
    real_load = game_service.load
    calls = {"n": 0}

    def load(gid: str) -> Any:
        calls["n"] += 1
        return stale if calls["n"] == 1 else real_load(gid)

    return load


class _HeldLock(asyncio.Lock):
    """Held by another request in this worker; waiting on it fails the test
    instead of hanging it."""

    async def acquire(self) -> bool:
        raise AssertionError("the route waited on a lock another request holds")


def test_process_turn_while_the_lock_is_held_is_409(client: TestClient) -> None:
    game_id, _ = _game_with_an_order(client)
    held = _HeldLock()
    asyncio.run(asyncio.Lock.acquire(held))
    assert held.locked()
    with patch("server.api.routes.games.get_process_turn_lock", return_value=held) as get_lock:
        resp = client.post(f"/games/{game_id}/process_turn", headers=BOT)
    get_lock.assert_called_once_with(game_id)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Turn processing already in progress for this game"
    assert game_service.meta(game_id)["phase_code"] == "S1901M"
    assert game_service._repo.get_pending_orders(game_id) == {"FRANCE": ["A PAR - BUR"]}


def test_a_draw_vote_on_a_game_that_ended_meanwhile_is_the_game_over_error(client: TestClient) -> None:
    game_id, tg = _game_with_an_order(client)
    load = _load_active_first(game_id)
    _end_in_a_draw(game_id)
    with patch.object(game_service, "load", side_effect=load):
        resp = client.post(f"/games/{game_id}/draw_vote", json=_as(tg, power="FRANCE", vote=True))
    assert resp.status_code == 409
    assert resp.json()["detail"] == f"Game {game_id} is {ALL_DRAWN}; draw votes are no longer accepted"
    assert game_service._repo.get_draw_votes(game_id) == {}


def test_a_deciding_vote_that_loses_to_a_draw_already_made_is_the_game_over_error(client: TestClient) -> None:
    """FRANCE's yes is recorded and reaches quorum, but before its draw is
    written a concurrent deciding vote has ended the game."""
    game_id, tg = _game_with_an_order(client)
    repo = game_service._repo
    real_modify = repo.modify_draw_votes

    def vote_then_someone_draws(*args: Any, **kwargs: Any) -> Any:
        votes = real_modify(*args, **kwargs)
        _end_in_a_draw(game_id)
        return votes

    with patch.object(repo, "modify_draw_votes", side_effect=vote_then_someone_draws):
        resp = client.post(f"/games/{game_id}/draw_vote", json=_as(tg, power="FRANCE", vote=True))
    assert resp.status_code == 409
    assert resp.json()["detail"] == f"Game {game_id} is {ALL_DRAWN}; draw votes are no longer accepted"
    assert game_service.load(game_id).state.winners == frozenset(
        {"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"}
    )


def test_a_concession_on_a_game_that_ended_meanwhile_is_refused_and_leaves_the_draw(client: TestClient) -> None:
    """A draw does not move the phase, so the phase guard alone let a concession
    computed before the draw write its still-active board over the finished game."""
    game_id, tg = _game_with_an_order(client)
    load = _load_active_first(game_id)
    _end_in_a_draw(game_id)
    with patch.object(game_service, "load", side_effect=load):
        resp = client.post(f"/games/{game_id}/concede", json=_as(tg, power="FRANCE"))
    assert resp.status_code == 409
    assert resp.json()["detail"] == f"Game {game_id} is {ALL_DRAWN}; a power can no longer concede"
    after = game_service.load(game_id).state
    assert after.status.value == "COMPLETED"
    assert game_service.meta(game_id)["status"] == "completed"
    assert any(u.power == "FRANCE" for u in after.units)


def test_adjudication_retries_running_out_is_409_and_changes_nothing(client: TestClient) -> None:
    game_id, _ = _game_with_an_order(client)
    repo = game_service._repo
    changed = PhaseInputsChangedError(
        f"game {game_id}: orders or the board changed while the turn was being adjudicated"
    )
    with patch.object(repo, "save_state", side_effect=changed) as save:
        resp = client.post(f"/games/{game_id}/process_turn", headers=BOT)
    assert save.call_count == _ADJUDICATION_ATTEMPTS == 5
    assert resp.status_code == 409
    assert resp.json()["detail"] == (
        f"game {game_id}: orders or the board changed while the turn was being adjudicated"
    )
    assert game_service.meta(game_id)["phase_code"] == "S1901M"
    assert repo.get_pending_orders(game_id) == {"FRANCE": ["A PAR - BUR"]}


def test_joining_a_finished_game_is_409(client: TestClient) -> None:
    game_id, _ = _game_with_an_order(client)
    _end_in_a_draw(game_id)
    late = _telegram_user(client, "latecomer")
    resp = client.post(f"/games/{game_id}/join", json=_as(late, power="ENGLAND"))
    assert resp.status_code == 409
    assert resp.json()["detail"] == f"Game {game_id} has ended; it cannot be joined."


def test_a_group_game_needs_the_real_bot_secret_not_any_body_secret(client: TestClient) -> None:
    """The header case is in ``test_group_games_api``; a bearer user who also
    puts a wrong ``bot_secret`` in the body is still not the bot."""
    email = f"chan_{time.time_ns()}@example.com"
    token = client.post("/auth/register", json={"email": email, "password": "testpass123"}).json()["access_token"]
    group = str(-(10**12) - time.time_ns() % 10**9)
    resp = client.post(
        "/games/create",
        json={"map_name": "standard", "channel_id": group, "bot_secret": BOT_SECRET + "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Only the bot creates a game for a Telegram group."
    assert client.get(f"/channels/{group}/game", headers=BOT).json() == {"linked": False}
