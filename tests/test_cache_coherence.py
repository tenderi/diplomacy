"""Cached reads must never show a player the world before their own write.

``GET /games/{id}/state`` (30 s), ``GET /games/{id}/players`` (60 s) and
``GET /users/{telegram_id}/games`` (60 s) are answered from ``response_cache``. Each
test warms the cache, makes a write through the API, and reads again: the read must
show the write, not a copy from before it.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.response_cache import clear_response_cache
from tests.conftest import _get_db_url
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

BOT = {"X-Bot-Secret": BOT_SECRET}


@pytest.fixture
def client() -> TestClient:
    clear_response_cache()
    return TestClient(app)


def _game(client: TestClient) -> tuple[str, str]:
    tg = _telegram_user(client, "cachey")
    game_id = str(client.post("/games/create", json=_as(tg, map_name="standard"), headers=BOT).json()["game_id"])
    return game_id, tg


def _state(client: TestClient, game_id: str) -> dict:
    return client.get(f"/games/{game_id}/state").json()


def _my_games(client: TestClient, tg: str) -> list[str]:
    return [str(g["game_id"]) for g in client.get(f"/users/{tg}/games", headers=BOT).json()["games"]]


def _seats(client: TestClient, game_id: str) -> dict[str, object]:
    return {p["power"]: p["telegram_id"] for p in client.get(f"/games/{game_id}/players").json()}


def test_joining_shows_in_my_games_and_the_seat_list(client: TestClient) -> None:
    game_id, tg = _game(client)
    assert game_id not in _my_games(client, tg) and _seats(client, game_id) == {}  # warm both
    assert client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE")).status_code == 200
    assert game_id in _my_games(client, tg)
    assert _seats(client, game_id) == {"FRANCE": tg}


def test_submitted_and_cleared_orders_show_in_the_state(client: TestClient) -> None:
    game_id, tg = _game(client)
    client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
    assert _state(client, game_id)["orders"] == {}  # warm
    assert client.post("/games/set_orders", json=_as(tg, game_id=game_id, power="FRANCE", orders=["A PAR - BUR"])).status_code == 200
    assert _state(client, game_id)["orders"] == {"FRANCE": ["A PAR - BUR"]}
    assert client.post(f"/games/{game_id}/orders/FRANCE/clear", json=_as(tg)).status_code == 200
    assert _state(client, game_id)["orders"] in ({}, {"FRANCE": []})


def test_a_processed_turn_shows_the_new_phase(client: TestClient) -> None:
    game_id, _tg = _game(client)
    assert _state(client, game_id)["phase"] == "S1901M"  # warm
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    assert _state(client, game_id)["phase"] == "F1901M"


def test_quitting_leaves_my_games_and_frees_the_seat(client: TestClient) -> None:
    game_id, tg = _game(client)
    client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
    assert game_id in _my_games(client, tg) and _seats(client, game_id) == {"FRANCE": tg}  # warm
    assert client.post(f"/games/{game_id}/quit", json=_as(tg)).status_code == 200
    assert game_id not in _my_games(client, tg)
    assert _seats(client, game_id) == {"FRANCE": None}


def test_taking_over_a_seat_shows_for_the_newcomer(client: TestClient) -> None:
    game_id, quitter = _game(client)
    client.post(f"/games/{game_id}/join", json=_as(quitter, power="FRANCE"))
    client.post(f"/games/{game_id}/quit", json=_as(quitter))
    newcomer = _telegram_user(client, "newcomer")
    assert _my_games(client, newcomer) == [] and _seats(client, game_id) == {"FRANCE": None}  # warm
    assert client.post(f"/games/{game_id}/replace", json=_as(newcomer, power="FRANCE")).status_code == 200
    assert _my_games(client, newcomer) == [game_id]
    assert _seats(client, game_id) == {"FRANCE": newcomer}


def test_a_draw_vote_and_a_dummy_show_in_the_state(client: TestClient) -> None:
    game_id, tg = _game(client)
    client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
    assert _state(client, game_id)["dummy_powers"] == []  # warm
    assert client.post(f"/games/{game_id}/dummies", json=_as(tg, power="ITALY", dummy=True)).status_code == 200
    assert _state(client, game_id)["dummy_powers"] == ["ITALY"]
