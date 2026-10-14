"""Routes guarded only by ``require_bot_or_user`` refuse a deactivated or deleted user (BH4).

Those routes never resolve the caller, so the dependency itself must check that the
user a decoded access token names still exists and is active. One test per route
family -- the game snapshot, the map-generation routes, the sandbox -- each showing
the token works while the account is active and is refused once it is not.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api.routes.auth import _create_access_token
from server.api.shared import db_service
from tests.conftest import _get_db_url

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

INACTIVE = (401, "User not found or inactive")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _registered(client: TestClient, prefix: str) -> tuple[int, dict[str, str]]:
    email = f"{prefix}_{time.time_ns()}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert reg.status_code == 200, reg.text
    body = reg.json()
    return int(body["user"]["id"]), {"Authorization": f"Bearer {body['access_token']}"}


def _game(client: TestClient, bearer: dict[str, str]) -> str:
    resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=bearer)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["game_id"])


def test_snapshot_refuses_an_inactive_users_token(client: TestClient) -> None:
    user_id, bearer = _registered(client, "bh4_snapshot")
    game_id = _game(client, bearer)
    ok = client.post(f"/games/{game_id}/snapshot", headers=bearer)
    assert (ok.status_code, ok.json()["status"]) == (200, "ok")

    db_service.set_user_active(user_id, False)
    r = client.post(f"/games/{game_id}/snapshot", headers=bearer)
    assert (r.status_code, r.json()["detail"]) == INACTIVE


def test_map_generation_refuses_an_inactive_users_token(client: TestClient) -> None:
    user_id, bearer = _registered(client, "bh4_maps")
    # An unknown game gets past auth to the route's own 404: the token is accepted.
    for path in ("/games/no-such-game/generate_map", "/games/no-such-game/generate_map/resolution"):
        ok = client.post(path, headers=bearer)
        assert (ok.status_code, ok.json()["detail"]) == (404, "Game not found"), path

    db_service.set_user_active(user_id, False)
    for path in ("/games/no-such-game/generate_map", "/games/no-such-game/generate_map/resolution"):
        r = client.post(path, headers=bearer)
        assert (r.status_code, r.json()["detail"]) == INACTIVE, path


def test_sandbox_refuses_an_inactive_users_token(client: TestClient) -> None:
    user_id, bearer = _registered(client, "bh4_sandbox")
    ok = client.post("/sandbox/start", json={}, headers=bearer)
    assert (ok.status_code, ok.json()["source_game_id"]) == (200, None)

    db_service.set_user_active(user_id, False)
    r = client.post("/sandbox/start", json={}, headers=bearer)
    assert (r.status_code, r.json()["detail"]) == INACTIVE


def test_a_deleted_users_token_is_refused(client: TestClient) -> None:
    bearer = {"Authorization": f"Bearer {_create_access_token(2147483647)}"}
    r = client.post("/sandbox/start", json={}, headers=bearer)
    assert (r.status_code, r.json()["detail"]) == INACTIVE


def test_the_bot_secret_still_works_alongside_an_inactive_token(client: TestClient) -> None:
    user_id, bearer = _registered(client, "bh4_bot")
    db_service.set_user_active(user_id, False)
    r = client.post("/sandbox/start", json={}, headers={**bearer, "X-Bot-Secret": "test_bot_secret_for_tests"})
    assert (r.status_code, r.json()["source_game_id"]) == (200, None)
