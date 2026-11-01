"""CC1: the per-game write routes that used to admit any signed-in account.

``POST /games/{id}/snapshot``, ``.../generate_map`` and ``.../generate_map/resolution``
depended only on ``require_bot_or_user``, which proves the caller is *someone*: any
account could add unbounded snapshot rows to, or force renders of, any game. They now
admit the bot secret, the game's seated players and its creator, and nobody else.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from server.api import app
from tests.conftest import _get_db_url

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

_BOT = {"X-Bot-Secret": "test_bot_secret_for_tests"}
_ROUTES = ("snapshot", "generate_map", "generate_map/resolution")
_NOT_A_PLAYER = (403, "You are not a player in this game.")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _bearer(client: TestClient, prefix: str) -> dict[str, str]:
    reg = client.post(
        "/auth/register", json={"email": f"{prefix}_{time.time_ns()}@example.com", "password": "testpass123"}
    )
    assert reg.status_code == 200, reg.text
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


@pytest.fixture
def game(client: TestClient) -> tuple[str, dict[str, str], dict[str, str], dict[str, str]]:
    """A game, its creator (not seated), a seated player and an outsider."""
    creator, player, outsider = (_bearer(client, p) for p in ("cc1_creator", "cc1_player", "cc1_outsider"))
    resp = client.post("/games/create", json={"map_name": "standard"}, headers=creator)
    assert resp.status_code == 200, resp.text
    game_id = str(resp.json()["game_id"])
    joined = client.post(f"/games/{game_id}/join", json={"power": "FRANCE"}, headers=player)
    assert joined.status_code == 200, joined.text
    return game_id, creator, player, outsider


@pytest.mark.parametrize("route", _ROUTES)
def test_an_unseated_signed_in_user_is_refused(client: TestClient, game: tuple, route: str) -> None:
    game_id, _, _, outsider = game
    r = client.post(f"/games/{game_id}/{route}", headers=outsider)
    assert (r.status_code, r.json()["detail"]) == _NOT_A_PLAYER


@pytest.mark.parametrize("route", _ROUTES)
@pytest.mark.parametrize("who", ["player", "creator", "bot"])
def test_a_seated_player_the_creator_and_the_bot_are_admitted(
    client: TestClient, game: tuple, route: str, who: str
) -> None:
    game_id, creator, player, _ = game
    headers = {"player": player, "creator": creator, "bot": _BOT}[who]
    r = client.post(f"/games/{game_id}/{route}", headers=headers)
    assert (r.status_code, r.json()["status"]) == (200, "ok")


def test_a_refused_snapshot_adds_no_row(client: TestClient, game: tuple) -> None:
    game_id, _, _, outsider = game
    before = client.get(f"/games/{game_id}/snapshots").json()["snapshots"]
    assert client.post(f"/games/{game_id}/snapshot", headers=outsider).status_code == 403
    assert client.get(f"/games/{game_id}/snapshots").json()["snapshots"] == before


def test_an_unknown_game_is_404_for_a_signed_in_user(client: TestClient) -> None:
    outsider = _bearer(client, "cc1_unknown")
    for route in _ROUTES:
        r = client.post(f"/games/999999999/{route}", headers=outsider)
        assert (r.status_code, r.json()["detail"]) == (404, "Game not found"), route


def test_no_credentials_is_still_401(client: TestClient, game: tuple) -> None:
    game_id = game[0]
    for route in _ROUTES:
        assert client.post(f"/games/{game_id}/{route}").status_code == 401, route
