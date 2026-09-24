"""
Comprehensive tests for authorization and security in API endpoints.

Tests that users can only perform actions for their assigned powers and games.
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


def _register_and_login(client, prefix="auth"):
    """Register a user and return Bearer auth headers."""
    email = f"{prefix}_{int(time.time() * 1000)}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert reg.status_code == 200, f"Registration failed: {reg.text}"
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_game(client, headers):
    """Create a game and return the game_id."""
    resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=headers)
    assert resp.status_code == 200, f"Game creation failed: {resp.text}"
    return resp.json()["game_id"]


@pytest.mark.unit
@pytest.mark.integration
class TestOrderSubmissionAuthorization:
    """Test authorization for order submission."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_can_submit_orders_for_own_power(self, client):
        """Test that user can submit orders for their assigned power."""
        headers = _register_and_login(client, "auth_user1")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "auth_user1", "full_name": "Auth User 1", "bot_secret": BOT_SECRET})
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user1",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "FRANCE"
        })

        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "auth_user1",
            "bot_secret": BOT_SECRET
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_cannot_submit_orders_for_other_power(self, client):
        """Test that user cannot submit orders for another user's power."""
        headers = _register_and_login(client, "auth_user2")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "auth_user2", "full_name": "Auth User 2", "bot_secret": BOT_SECRET})
        client.post("/users/persistent_register", json={"telegram_id": "auth_user3", "full_name": "Auth User 3", "bot_secret": BOT_SECRET})
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user2",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user3",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "GERMANY"
        })

        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "GERMANY",
            "orders": ["A BER - SIL"],
            "telegram_id": "auth_user2",
            "bot_secret": BOT_SECRET
        })
        assert resp.status_code == 403, f"Expected 403 Forbidden, got {resp.status_code}"
        assert "not authorized" in resp.json().get("detail", "").lower() or \
               "unauthorized" in resp.json().get("detail", "").lower()

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_unregistered_user_cannot_submit_orders(self, client):
        """Test that unregistered users cannot submit orders."""
        headers = _register_and_login(client, "auth_create3")
        game_id = _create_game(client, headers)

        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "unregistered_user",
            "bot_secret": BOT_SECRET
        })
        assert resp.status_code in [401, 403, 404], \
            f"Expected 401, 403, or 404, got {resp.status_code}: {resp.json()}"

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_not_in_game_cannot_submit_orders(self, client):
        """Test that users not in a game cannot submit orders for that game."""
        headers = _register_and_login(client, "auth_create4")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "auth_user4", "full_name": "Auth User 4", "bot_secret": BOT_SECRET})

        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "auth_user4",
            "bot_secret": BOT_SECRET
        })
        assert resp.status_code == 404, \
            f"Expected 404 Not Found, got {resp.status_code}: {resp.json()}"


@pytest.mark.unit
@pytest.mark.integration
class TestOrderClearAuthorization:
    """Test authorization for clearing orders."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_can_clear_own_orders(self, client):
        """Test that user can clear orders for their assigned power."""
        headers = _register_and_login(client, "auth_clear5")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "auth_user5", "full_name": "Auth User 5", "bot_secret": BOT_SECRET})
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user5",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "auth_user5",
            "bot_secret": BOT_SECRET
        })

        resp = client.post(f"/games/{game_id}/orders/FRANCE/clear", json={
            "telegram_id": "auth_user5",
            "bot_secret": BOT_SECRET
        })
        assert resp.status_code == 200

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_cannot_clear_other_power_orders(self, client):
        """Test that user cannot clear orders for another user's power."""
        headers = _register_and_login(client, "auth_clear6")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "auth_user6", "full_name": "Auth User 6", "bot_secret": BOT_SECRET})
        client.post("/users/persistent_register", json={"telegram_id": "auth_user7", "full_name": "Auth User 7", "bot_secret": BOT_SECRET})
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user6",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user7",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "GERMANY"
        })
        client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "GERMANY",
            "orders": ["A BER - SIL"],
            "telegram_id": "auth_user7",
            "bot_secret": BOT_SECRET
        })

        resp = client.post(f"/games/{game_id}/orders/GERMANY/clear", json={
            "telegram_id": "auth_user6",
            "bot_secret": BOT_SECRET
        })
        assert resp.status_code == 403, \
            f"Expected 403 Forbidden, got {resp.status_code}: {resp.json()}"


@pytest.mark.unit
@pytest.mark.integration
class TestMessageAuthorization:
    """Test authorization for sending messages."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_can_send_message_if_in_game(self, client):
        """Test that users in a game can send messages."""
        headers = _register_and_login(client, "auth_msg8")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "auth_user8", "full_name": "Auth User 8", "bot_secret": BOT_SECRET})
        client.post("/users/persistent_register", json={"telegram_id": "auth_user9", "full_name": "Auth User 9", "bot_secret": BOT_SECRET})
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user8",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user9",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "GERMANY"
        })

        resp = client.post(f"/games/{game_id}/message", json={
            "telegram_id": "auth_user8",
            "bot_secret": BOT_SECRET,
            "recipient_power": "GERMANY",
            "text": "Hello"
        })
        if resp.status_code != 200:
            print(f"Error response: {resp.json()}")
        assert resp.status_code == 200

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_not_in_game_cannot_send_message(self, client):
        """Test that users not in a game cannot send messages."""
        headers = _register_and_login(client, "auth_msg10")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "auth_user10", "full_name": "Auth User 10", "bot_secret": BOT_SECRET})

        resp = client.post(f"/games/{game_id}/message", json={
            "telegram_id": "auth_user10",
            "bot_secret": BOT_SECRET,
            "recipient_power": "FRANCE",
            "text": "Hello"
        })
        assert resp.status_code == 403, \
            f"Expected 403 Forbidden, got {resp.status_code}: {resp.json()}"


@pytest.mark.unit
@pytest.mark.integration
class TestGameManagementAuthorization:
    """Test authorization for game management actions."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_can_quit_own_game(self, client):
        """Test that users can quit games they're in."""
        headers = _register_and_login(client, "auth_quit11")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "auth_user11", "full_name": "Auth User 11", "bot_secret": BOT_SECRET})
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user11",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "FRANCE"
        })

        resp = client.post(f"/games/{game_id}/quit", json={
            "telegram_id": "auth_user11",
            "bot_secret": BOT_SECRET,
            "power": "FRANCE"
        })
        assert resp.status_code == 200

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_cannot_quit_other_power(self, client):
        """Test that users cannot quit another user's power."""
        headers = _register_and_login(client, "auth_quit12")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "auth_user12", "full_name": "Auth User 12", "bot_secret": BOT_SECRET})
        client.post("/users/persistent_register", json={"telegram_id": "auth_user13", "full_name": "Auth User 13", "bot_secret": BOT_SECRET})
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user12",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user13",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "GERMANY"
        })

        resp = client.post(f"/games/{game_id}/quit", json={
            "telegram_id": "auth_user12",
            "bot_secret": BOT_SECRET,
            "power": "GERMANY"
        })
        assert resp.status_code in [401, 403, 404], \
            f"Expected 401, 403, or 404, got {resp.status_code}: {resp.json()}"


@pytest.mark.unit
@pytest.mark.integration
class TestBearerTokenAuthorization:
    """Test authorization using Bearer tokens."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_bearer_token_authorization(self, client):
        """Test that Bearer token authentication works."""
        headers = _register_and_login(client, "bearer_test")
        game_id = _create_game(client, headers)

        join_resp = client.post(f"/games/{int(game_id)}/join", json={
            "game_id": int(game_id),
            "power": "FRANCE"
        }, headers=headers)
        assert join_resp.status_code == 200

        orders_resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"]
        }, headers=headers)
        assert orders_resp.status_code == 200

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_invalid_bearer_token_rejected(self, client):
        """Test that invalid Bearer tokens are rejected."""
        headers = {"Authorization": "Bearer invalid_token_12345"}
        resp = client.get("/users/me/games", headers=headers)
        assert resp.status_code == 401, \
            f"Expected 401 Unauthorized, got {resp.status_code}: {resp.json()}"
