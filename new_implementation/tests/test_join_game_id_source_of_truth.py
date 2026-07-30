"""Joining a game needs the game id in exactly one place (G6).

`POST /games/{game_id}/join` bound `game_id` from the path *and* required it in
the body, so omitting it from the body was a 422 even though the value was right
there in the URL — while supplying a **different** value than the path was
accepted without complaint. The second half is the dangerous one: a client bug
that sent the wrong id looked like a successful join.

The body field stays (about forty existing callers send it) but is now optional,
and a value that disagrees with the path is a 400. Silently accepting a mismatch
was the one option G6 ruled out.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared

pytestmark = [pytest.mark.integration, pytest.mark.database]


def _headers(client: TestClient) -> dict:
    stamp = f"{int(time.time() * 1000000)}"
    resp = client.post(
        "/auth/register",
        json={"email": f"join_{stamp}@example.com", "password": "testpass123"},
    )
    if resp.status_code != 200:
        pytest.skip("Database not available for join test")
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _game(client: TestClient, headers: dict) -> str:
    resp = client.post(
        "/games/create",
        json={"map_name": "standard", "initial_phase": "Movement"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["game_id"])


def test_join_without_game_id_in_body_succeeds() -> None:
    """The path is enough. This used to be a 422."""
    client = TestClient(app)
    headers = _headers(client)
    game_id = _game(client, headers)

    resp = client.post(
        f"/games/{game_id}/join", json={"power": "FRANCE"}, headers=headers
    )
    assert resp.status_code == 200, resp.text

    players = client.get(f"/games/{game_id}/players").json()
    assert any(p.get("power") == "FRANCE" for p in players), players


def test_join_with_a_matching_game_id_still_succeeds() -> None:
    """Every existing caller sends it; none may regress."""
    client = TestClient(app)
    headers = _headers(client)
    game_id = _game(client, headers)

    resp = client.post(
        f"/games/{game_id}/join",
        json={"game_id": int(game_id), "power": "GERMANY"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


def test_join_with_a_mismatched_game_id_is_rejected() -> None:
    """The behaviour G6 ruled out: silently accepting the wrong id.

    Before this, the body value was simply ignored, so a client that sent the
    wrong id got a 200 and a player row in the game named by the *path* — a bug
    that looks exactly like success.
    """
    client = TestClient(app)
    headers = _headers(client)
    game_id = _game(client, headers)
    other_id = _game(client, headers)
    assert game_id != other_id

    resp = client.post(
        f"/games/{game_id}/join",
        json={"game_id": int(other_id), "power": "ITALY"},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert str(other_id) in detail and str(game_id) in detail, detail
    assert "optional" in detail.lower(), "the error should say what to do instead"

    # And nothing was joined, in either game.
    for gid in (game_id, other_id):
        players = client.get(f"/games/{gid}/players").json()
        assert not any(p.get("power") == "ITALY" for p in players), (gid, players)


def test_unauthenticated_create_says_which_credentials_are_accepted() -> None:
    """G6's `/games/create` decision: keep the auth, fix the opaque error.

    The requirement stays — an unauthenticated game-creation endpoint is a spam
    vector. What made it feel like a wart was a bare "Not authenticated" with no
    hint that a header was missing.
    """
    client = TestClient(app)
    resp = client.post("/games/create", json={"map_name": "standard"})
    assert resp.status_code == 401, resp.text
    detail = resp.json()["detail"]
    assert "Bearer" in detail, detail
    assert "X-Bot-Secret" in detail, detail


def test_bot_secret_can_still_create_a_game() -> None:
    """The other accepted credential must keep working."""
    if not api_shared.BOT_SECRET:
        pytest.skip("No bot secret configured in this environment")
    client = TestClient(app)
    resp = client.post(
        "/games/create",
        json={"map_name": "standard"},
        headers={"X-Bot-Secret": api_shared.BOT_SECRET},
    )
    assert resp.status_code == 200, resp.text
