"""DY2: overlapping registrations and a clear racing a turn change."""

import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from server._api_module import app
from server.api.routes import auth as auth_routes
from server.api.routes import users as users_routes
from server.api.routes.orders import game_service as route_game_service
from server.game_service import StaleGameError
from tests.bot_client import BotTestClient
from tests.conftest import _get_db_url

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured"),
]

BOT_SECRET = "test_bot_secret_for_tests"


@pytest.fixture
def client():
    return BotTestClient(app)


def _uniq() -> str:
    return str(int(time.time() * 1000000))


def test_register_duplicate_email_race_says_email(client):
    email = f"dy2_{_uniq()}@example.com"
    first = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert first.status_code == 200, first.text
    # The pre-check misses (the other registration had not committed yet); the
    # re-query after the IntegrityError finds the email.
    real = auth_routes.db_service.get_user_by_email
    calls = {"n": 0}

    def miss_first(e):
        calls["n"] += 1
        return None if calls["n"] == 1 else real(e)

    with patch.object(auth_routes.db_service, "get_user_by_email", side_effect=miss_first):
        resp = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "Email already registered"


def test_register_duplicate_nickname_race_says_nickname(client):
    nick = f"Dy{_uniq()[-8:]}"
    first = client.post(
        "/auth/register", json={"email": f"dy2a_{_uniq()}@example.com", "password": "testpass123", "nickname": nick}
    )
    assert first.status_code == 200, first.text
    with patch.object(auth_routes.db_service, "nickname_taken", return_value=False):
        resp = client.post(
            "/auth/register",
            json={"email": f"dy2b_{_uniq()}@example.com", "password": "testpass123", "nickname": nick},
        )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "That nickname is taken"


def test_persistent_register_race_returns_already_registered(client):
    tg = f"dy2tg_{_uniq()}"
    first = client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": tg})
    assert first.status_code == 200, first.text
    real = users_routes.db_service.get_user_by_telegram_id
    calls = {"n": 0}

    def miss_first(telegram_id):
        calls["n"] += 1
        return None if calls["n"] == 1 else real(telegram_id)

    with patch.object(users_routes.db_service, "get_user_by_telegram_id", side_effect=miss_first):
        resp = client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": tg})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "already_registered"
    assert body["user_id"] == first.json()["user_id"]
    assert body["telegram_id"] == tg


def _game_with_orders(client):
    reg = client.post("/auth/register", json={"email": f"dy2g_{_uniq()}@example.com", "password": "testpass123"})
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=headers)
    gid = str(resp.json()["game_id"])
    tg = f"dy2c_{_uniq()}"
    client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": tg})
    client.post(
        f"/games/{gid}/join",
        json={"telegram_id": tg, "bot_secret": BOT_SECRET, "game_id": int(gid), "power": "FRANCE"},
    )
    return gid, tg


def test_clear_orders_refuses_a_stale_phase(client):
    gid, _ = _game_with_orders(client)
    route_game_service._repo.modify_pending_orders(gid, lambda p: {**p, "FRANCE": ["A PAR H"]})
    with pytest.raises(StaleGameError):
        route_game_service.clear_orders(gid, "FRANCE", expected_phase_code="F1950M")
    assert route_game_service._repo.modify_pending_orders(gid, lambda p: p)["FRANCE"] == ["A PAR H"]
    route_game_service.clear_orders(gid, "FRANCE", expected_phase_code=route_game_service.load(gid).state.phase_name)
    assert "FRANCE" not in route_game_service._repo.modify_pending_orders(gid, lambda p: p)


def test_clear_route_returns_409_when_the_turn_moved(client):
    gid, tg = _game_with_orders(client)
    stale = SimpleNamespace(state=SimpleNamespace(phase_name="F1950M"))
    with patch.object(route_game_service, "load", return_value=stale):
        resp = client.post(f"/games/{gid}/orders/FRANCE/clear", json={"telegram_id": tg, "bot_secret": BOT_SECRET})
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == (
        "The turn was processed while your orders were being cleared; none were cleared. "
        "Check the new board and try again."
    )
