"""A deactivated account (``users.is_active = False``) gets nothing from its credentials.

Login (``/auth/login`` and the OAuth2 ``/auth/token``) refuses it even with the right
password, a refresh token issued before the deactivation stops working, and so does an
access token: by the ``get_current_user`` dependency and by ``resolve_user_or_telegram``.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api.shared import db_service
from tests.conftest import _get_db_url

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

PASSWORD = "testpass123"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _registered(client: TestClient, prefix: str) -> tuple[str, dict]:
    email = f"{prefix}_{time.time_ns()}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert reg.status_code == 200, reg.text
    return email, reg.json()


def _deactivate(body: dict) -> None:
    db_service.set_user_active(int(body["user"]["id"]), False)


def test_an_inactive_account_cannot_log_in(client: TestClient) -> None:
    email, body = _registered(client, "inactive_login")
    _deactivate(body)
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert (r.status_code, r.json()["detail"]) == (401, "Account inactive")


def test_an_inactive_account_cannot_get_a_token_from_the_oauth2_endpoint(client: TestClient) -> None:
    email, body = _registered(client, "inactive_token")
    _deactivate(body)
    r = client.post("/auth/token", data={"username": email, "password": PASSWORD})
    assert (r.status_code, r.json()["detail"]) == (401, "Account inactive")


def test_a_wrong_password_on_an_inactive_account_does_not_reveal_it(client: TestClient) -> None:
    email, body = _registered(client, "inactive_wrongpw")
    _deactivate(body)
    r = client.post("/auth/login", json={"email": email, "password": "not-the-password"})
    assert (r.status_code, r.json()["detail"]) == (401, "Invalid email or password")


def test_an_inactive_account_cannot_refresh(client: TestClient) -> None:
    _email, body = _registered(client, "inactive_refresh")
    _deactivate(body)
    r = client.post("/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert (r.status_code, r.json()["detail"]) == (401, "User not found or inactive")


def test_an_existing_access_token_stops_resolving(client: TestClient) -> None:
    _email, body = _registered(client, "inactive_bearer")
    bearer = {"Authorization": f"Bearer {body['access_token']}"}
    assert client.get("/auth/me", headers=bearer).status_code == 200
    _deactivate(body)

    me = client.get("/auth/me", headers=bearer)
    assert (me.status_code, me.json()["detail"]) == (401, "User not found or inactive")
    games = client.get("/users/me/games", headers=bearer)
    assert (games.status_code, games.json()["detail"]) == (401, "User not found or inactive")
    # The routes that also accept a Telegram id resolve the caller through
    # ``resolve_user_or_telegram``: same refusal.
    feedback = client.post("/feedback", json={"text": "hello"}, headers=bearer)
    assert (feedback.status_code, feedback.json()["detail"]) == (401, "Not authenticated")


def test_reactivating_restores_access(client: TestClient) -> None:
    email, body = _registered(client, "inactive_back")
    _deactivate(body)
    db_service.set_user_active(int(body["user"]["id"]), True)
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert (r.status_code, r.json()["user"]["email"]) == (200, email)


def test_deactivating_an_unknown_user_is_an_error() -> None:
    with pytest.raises(ValueError, match="User 2147483647 not found"):
        db_service.set_user_active(2147483647, False)
