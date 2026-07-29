"""D3/C3: API tests for /games/{id}/draw_vote, /draw_vote_status, /concede.

Mirrors tests/test_api_routes_orders.py's fixtures and auth-check style --
the same `_authorize_power` helper backs both `set_orders` and these routes.
"""
import time

import pytest
from fastapi.testclient import TestClient

from server.api import app
from tests.conftest import _get_db_url

BOT_SECRET = "test_bot_secret_for_tests"


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def _register_and_login(client, prefix="drawvote"):
    """Register a user and return Bearer auth headers."""
    email = f"{prefix}_{int(time.time() * 1000)}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert reg.status_code == 200, f"Registration failed: {reg.text}"
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


def _create_game(client, headers):
    """Create a game with auth and return game_id."""
    resp = client.post("/games/create", json={"map_name": "standard"}, headers=headers)
    assert resp.status_code == 200, f"Game creation failed: {resp.text}"
    return resp.json()["game_id"]


@pytest.mark.unit
class TestDrawVote:
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_draw_vote_success(self, client):
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "dv_user1", "full_name": "Test"})
        headers = _register_and_login(client, "dv_ok")
        game_id = _create_game(client, headers)
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "dv_user1", "bot_secret": BOT_SECRET, "game_id": int(game_id), "power": "FRANCE"})

        resp = client.post(f"/games/{game_id}/draw_vote", json={
            "power": "FRANCE", "vote": True,
            "telegram_id": "dv_user1", "bot_secret": BOT_SECRET,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "recorded"
        assert data["quorum_reached"] is False
        assert "FRANCE" in data["votes"]

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_draw_vote_unauthorized(self, client):
        """A user who does not hold the power gets 403, not a silently-cast vote."""
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "dv_owner", "full_name": "Owner"})
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "dv_other", "full_name": "Other"})
        headers = _register_and_login(client, "dv_unauth")
        game_id = _create_game(client, headers)
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "dv_owner", "bot_secret": BOT_SECRET, "game_id": int(game_id), "power": "FRANCE"})

        resp = client.post(f"/games/{game_id}/draw_vote", json={
            "power": "FRANCE", "vote": True,
            "telegram_id": "dv_other", "bot_secret": BOT_SECRET,
        })
        assert resp.status_code == 403

        # And the vote was never recorded.
        status = client.get(f"/games/{game_id}/draw_vote_status")
        assert status.status_code == 200
        assert status.json()["votes"] == []

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_draw_vote_bearer_auth_wrong_user(self, client):
        """Same check via Bearer token instead of telegram_id+bot_secret."""
        owner_headers = _register_and_login(client, "dv_bearer_owner")
        other_headers = _register_and_login(client, "dv_bearer_other")
        game_id = _create_game(client, owner_headers)
        client.post(f"/games/{int(game_id)}/join", json={"game_id": int(game_id), "power": "FRANCE"}, headers=owner_headers)

        resp = client.post(f"/games/{game_id}/draw_vote", json={"power": "FRANCE", "vote": True}, headers=other_headers)
        assert resp.status_code == 403

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_draw_vote_game_not_found(self, client):
        """No auth at all -- _authorize_power rejects before the game lookup runs."""
        resp = client.post("/games/nonexistent-game/draw_vote", json={"power": "FRANCE", "vote": True})
        assert resp.status_code in (401, 403, 404)

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_draw_vote_status_no_auth_required(self, client):
        headers = _register_and_login(client, "dv_status")
        game_id = _create_game(client, headers)

        resp = client.get(f"/games/{game_id}/draw_vote_status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["required"] == sorted(
            ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]
        )
        assert data["votes"] == []
        assert data["quorum_reached"] is False

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_draw_vote_status_game_not_found(self, client):
        resp = client.get("/games/nonexistent-game/draw_vote_status")
        assert resp.status_code == 404


@pytest.mark.unit
class TestConcede:
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_concede_success(self, client):
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "cc_user1", "full_name": "Test"})
        headers = _register_and_login(client, "cc_ok")
        game_id = _create_game(client, headers)
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "cc_user1", "bot_secret": BOT_SECRET, "game_id": int(game_id), "power": "FRANCE"})

        resp = client.post(f"/games/{game_id}/concede", json={
            "power": "FRANCE", "telegram_id": "cc_user1", "bot_secret": BOT_SECRET,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["power"] == "FRANCE"
        # Conceding one power out of seven never ends the game.
        assert data["game_status"] == "ACTIVE"

        state = client.get(f"/games/{game_id}/state")
        assert state.status_code == 200
        assert state.json()["status"] == "ACTIVE"
        assert "FRANCE" not in {u["power"] for u in state.json()["units"]}

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_concede_unauthorized(self, client):
        """A user who does not hold the power gets 403, and its units stay put."""
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "cc_owner", "full_name": "Owner"})
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "cc_other", "full_name": "Other"})
        headers = _register_and_login(client, "cc_unauth")
        game_id = _create_game(client, headers)
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "cc_owner", "bot_secret": BOT_SECRET, "game_id": int(game_id), "power": "FRANCE"})

        resp = client.post(f"/games/{game_id}/concede", json={
            "power": "FRANCE", "telegram_id": "cc_other", "bot_secret": BOT_SECRET,
        })
        assert resp.status_code == 403

        state = client.get(f"/games/{game_id}/state")
        assert "FRANCE" in {u["power"] for u in state.json()["units"]}

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_concede_bearer_auth_wrong_user(self, client):
        owner_headers = _register_and_login(client, "cc_bearer_owner")
        other_headers = _register_and_login(client, "cc_bearer_other")
        game_id = _create_game(client, owner_headers)
        client.post(f"/games/{int(game_id)}/join", json={"game_id": int(game_id), "power": "FRANCE"}, headers=owner_headers)

        resp = client.post(f"/games/{game_id}/concede", json={"power": "FRANCE"}, headers=other_headers)
        assert resp.status_code == 403

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_concede_game_not_found(self, client):
        """No auth at all -- _authorize_power rejects before the game lookup runs."""
        resp = client.post("/games/nonexistent-game/concede", json={"power": "FRANCE"})
        assert resp.status_code in (401, 403, 404)
