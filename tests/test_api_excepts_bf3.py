"""BF3: the remaining API routes no longer wrap handlers in a blanket `except Exception`.

A programming bug is a plain 500 (traceback in the log) rather than a 500 whose detail is
the exception's text; storage failures that must not break a request stay narrow.
"""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from server.api import ADMIN_TOKEN, app
from server.api import shared as api_shared
from server.api.routes import auth as auth_routes
from server.api.routes import maps as maps_routes

pytestmark = [pytest.mark.integration, pytest.mark.database]

SECRET = "test_bot_secret_for_tests"
BOT = {"X-Bot-Secret": SECRET}
ADMIN = {"X-Admin-Token": ADMIN_TOKEN}


@pytest.fixture
def crash_client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _boom(*_: Any, **__: Any) -> Any:
    raise TypeError("secret internal detail")


def test_a_bug_in_an_admin_route_is_a_plain_500(
    crash_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api_shared.db_service, "get_game_count", _boom)
    r = crash_client.get("/admin/games_count", headers=ADMIN)
    assert r.status_code == 500
    assert r.text == "Internal Server Error"


def test_an_admin_route_still_returns_its_count(api_client: TestClient) -> None:
    r = api_client.get("/admin/users_count", headers=ADMIN)
    assert r.status_code == 200
    assert isinstance(r.json()["count"], int)


def test_a_bug_in_channel_info_is_a_plain_500(
    crash_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api_shared.db_service, "get_game_channel_info", _boom)
    r = crash_client.get("/games/any_game/channel", headers=BOT)
    assert r.status_code == 500
    assert r.text == "Internal Server Error"


def test_a_bug_in_persistent_register_is_a_plain_500(
    crash_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api_shared.db_service, "get_user_by_telegram_id", _boom)
    r = crash_client.post("/users/persistent_register", json={"telegram_id": "424242", "bot_secret": SECRET})
    assert r.status_code == 500
    assert r.text == "Internal Server Error"


def test_a_bug_in_the_map_render_is_a_plain_500(
    crash_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(maps_routes.Map, "render_board_png", _boom)
    r = crash_client.get("/maps/standard/preview.png")
    assert r.status_code == 500
    assert r.text == "Internal Server Error"


def test_a_malformed_stored_password_hash_does_not_verify() -> None:
    assert auth_routes._verify_password("secret", "not-a-bcrypt-hash") is False


def test_a_failing_idempotency_store_does_not_break_the_request(
    crash_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(*_: Any, **__: Any) -> Any:
        raise OperationalError("SELECT 1", {}, Exception("db down"))

    monkeypatch.setattr(api_shared.db_service, "get_idempotent_response", down)
    monkeypatch.setattr(api_shared.db_service, "store_idempotent_response", down)
    r = crash_client.post(
        "/users/persistent_register",
        json={"telegram_id": "424243", "bot_secret": SECRET},
        headers={**BOT, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 200
    assert r.json()["telegram_id"] == "424243"
