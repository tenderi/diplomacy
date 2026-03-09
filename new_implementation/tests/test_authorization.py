"""
Comprehensive tests for authorization and security in API endpoints.

Tests that users can only perform actions for their assigned powers and games.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from server.api import app
from tests.conftest import _get_db_url


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.mark.unit
@pytest.mark.integration
class TestOrderSubmissionAuthorization:
    """Test authorization for order submission."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_can_submit_orders_for_own_power(self, client):
        """Test that user can submit orders for their assigned power."""
        # Setup: register user, create game, join
        client.post("/users/persistent_register", json={"telegram_id": "auth_user1", "full_name": "Auth User 1"})
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user1",
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        
        # Submit orders for own power
        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "auth_user1"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_cannot_submit_orders_for_other_power(self, client):
        """Test that user cannot submit orders for another user's power."""
        # Setup: register two users, create game, join different powers
        client.post("/users/persistent_register", json={"telegram_id": "auth_user2", "full_name": "Auth User 2"})
        client.post("/users/persistent_register", json={"telegram_id": "auth_user3", "full_name": "Auth User 3"})
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user2",
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user3",
            "game_id": int(game_id),
            "power": "GERMANY"
        })
        
        # User 2 tries to submit orders for User 3's power (GERMANY)
        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "GERMANY",  # User 3's power
            "orders": ["A BER - SIL"],
            "telegram_id": "auth_user2"  # User 2 trying to order User 3's power
        })
        assert resp.status_code == 403, f"Expected 403 Forbidden, got {resp.status_code}"
        assert "not authorized" in resp.json().get("detail", "").lower() or \
               "unauthorized" in resp.json().get("detail", "").lower()
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_unregistered_user_cannot_submit_orders(self, client):
        """Test that unregistered users cannot submit orders."""
        # Create game without joining
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        
        # Try to submit orders without being registered or in game
        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "unregistered_user"
        })
        # Should return 401 (not authenticated), 403 (forbidden), or 404 (not found)
        assert resp.status_code in [401, 403, 404], \
            f"Expected 401, 403, or 404, got {resp.status_code}: {resp.json()}"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_not_in_game_cannot_submit_orders(self, client):
        """Test that users not in a game cannot submit orders for that game."""
        # Setup: register user, create game (but don't join)
        client.post("/users/persistent_register", json={"telegram_id": "auth_user4", "full_name": "Auth User 4"})
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        
        # Try to submit orders without joining game
        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "auth_user4"
        })
        # Should return 404 (player not found) since user is not in game
        assert resp.status_code == 404, \
            f"Expected 404 Not Found, got {resp.status_code}: {resp.json()}"


@pytest.mark.unit
@pytest.mark.integration
class TestOrderClearAuthorization:
    """Test authorization for clearing orders."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_can_clear_own_orders(self, client):
        """Test that user can clear orders for their assigned power."""
        # Setup
        client.post("/users/persistent_register", json={"telegram_id": "auth_user5", "full_name": "Auth User 5"})
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user5",
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        
        # Submit orders first
        client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "auth_user5"
        })
        
        # Clear orders
        resp = client.post(f"/games/{game_id}/orders/FRANCE/clear", json={
            "telegram_id": "auth_user5"
        })
        assert resp.status_code == 200
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_cannot_clear_other_power_orders(self, client):
        """Test that user cannot clear orders for another user's power."""
        # Setup: two users, different powers
        client.post("/users/persistent_register", json={"telegram_id": "auth_user6", "full_name": "Auth User 6"})
        client.post("/users/persistent_register", json={"telegram_id": "auth_user7", "full_name": "Auth User 7"})
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user6",
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user7",
            "game_id": int(game_id),
            "power": "GERMANY"
        })
        
        # User 7 submits orders
        client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "GERMANY",
            "orders": ["A BER - SIL"],
            "telegram_id": "auth_user7"
        })
        
        # User 6 tries to clear User 7's orders
        resp = client.post(f"/games/{game_id}/orders/GERMANY/clear", json={
            "telegram_id": "auth_user6"  # Wrong user
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
        # Setup
        client.post("/users/persistent_register", json={"telegram_id": "auth_user8", "full_name": "Auth User 8"})
        client.post("/users/persistent_register", json={"telegram_id": "auth_user9", "full_name": "Auth User 9"})
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user8",
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user9",
            "game_id": int(game_id),
            "power": "GERMANY"
        })
        
        # Send message
        resp = client.post(f"/games/{game_id}/message", json={
            "telegram_id": "auth_user8",
            "recipient_power": "GERMANY",
            "text": "Hello"
        })
        if resp.status_code != 200:
            print(f"Error response: {resp.json()}")
        assert resp.status_code == 200
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_not_in_game_cannot_send_message(self, client):
        """Test that users not in a game cannot send messages."""
        # Setup: register user, create game (but don't join)
        client.post("/users/persistent_register", json={"telegram_id": "auth_user10", "full_name": "Auth User 10"})
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        
        # Try to send message without being in game
        resp = client.post(f"/games/{game_id}/message", json={
            "telegram_id": "auth_user10",
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
        # Setup
        client.post("/users/persistent_register", json={"telegram_id": "auth_user11", "full_name": "Auth User 11"})
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user11",
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        
        # Quit game
        resp = client.post(f"/games/{game_id}/quit", json={
            "telegram_id": "auth_user11",
            "power": "FRANCE"
        })
        assert resp.status_code == 200
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_cannot_quit_other_power(self, client):
        """Test that users cannot quit another user's power."""
        # Setup: two users
        client.post("/users/persistent_register", json={"telegram_id": "auth_user12", "full_name": "Auth User 12"})
        client.post("/users/persistent_register", json={"telegram_id": "auth_user13", "full_name": "Auth User 13"})
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user12",
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "auth_user13",
            "game_id": int(game_id),
            "power": "GERMANY"
        })
        
        # User 12 tries to quit User 13's power
        resp = client.post(f"/games/{game_id}/quit", json={
            "telegram_id": "auth_user12",
            "power": "GERMANY"  # User 13's power
        })
        # Should return 401 (not authenticated), 403 (forbidden), or 404 (not found)
        assert resp.status_code in [401, 403, 404], \
            f"Expected 401, 403, or 404, got {resp.status_code}: {resp.json()}"


@pytest.mark.unit
@pytest.mark.integration
class TestBearerTokenAuthorization:
    """Test authorization using Bearer tokens."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_bearer_token_authorization(self, client):
        """Test that Bearer token authentication works."""
        # Register user and get token
        import time
        unique_email = f"bearer_test_{int(time.time() * 1000)}@example.com"
        register_resp = client.post("/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "full_name": "Bearer Test User"
        })
        assert register_resp.status_code == 200, f"Registration failed: {register_resp.json()}"
        token = register_resp.json()["access_token"]
        
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        
        # Join game using Bearer token
        headers = {"Authorization": f"Bearer {token}"}
        join_resp = client.post(f"/games/{int(game_id)}/join", json={
            "game_id": int(game_id),
            "power": "FRANCE"
        }, headers=headers)
        assert join_resp.status_code == 200
        
        # Submit orders using Bearer token
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
        
        # Try to access protected endpoint
        resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=headers)
        # Create game might not require auth, so try a protected endpoint
        # Try to get user games (requires auth)
        resp = client.get("/users/me/games", headers=headers)
        assert resp.status_code == 401, \
            f"Expected 401 Unauthorized, got {resp.status_code}: {resp.json()}"
