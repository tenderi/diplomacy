"""
Comprehensive tests for error handling and HTTP status codes.

Tests that all error conditions return correct HTTP status codes
and that error messages are clear and helpful.
"""
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from server.api import app
from tests.conftest import _get_db_url


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.mark.unit
@pytest.mark.integration
class TestHTTPStatusCodes:
    """Test that correct HTTP status codes are returned for various scenarios."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_400_bad_request_missing_fields(self, client):
        """Test 400 Bad Request for missing required fields."""
        # Note: /games/create has map_name with default "standard", so empty body is valid
        # Test with set_orders which has required fields
        resp = client.post("/games/set_orders", json={
            "game_id": "123"
            # Missing power, orders (required fields)
        })
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.json()}"  # FastAPI uses 422 for validation errors
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_403_forbidden_unauthorized_action(self, client):
        """Test 403 Forbidden for unauthorized actions."""
        # Setup: two users, one tries to act for other's power
        client.post("/users/persistent_register", json={"telegram_id": "error_user1", "full_name": "Error User 1"})
        client.post("/users/persistent_register", json={"telegram_id": "error_user2", "full_name": "Error User 2"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "error_user1",
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        
        # User 2 tries to submit orders for User 1's power
        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "error_user2"  # Not authorized
        })
        assert resp.status_code == 403, f"Expected 403 Forbidden, got {resp.status_code}: {resp.json()}"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_404_not_found_game(self, client):
        """Test 404 Not Found for non-existent game."""
        resp = client.get("/games/99999/state")
        assert resp.status_code == 404, f"Expected 404 Not Found, got {resp.status_code}: {resp.json()}"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_404_not_found_power(self, client):
        """Test 404 Not Found for non-existent power."""
        client.post("/users/persistent_register", json={"telegram_id": "error_user3", "full_name": "Error User 3"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        # Try to submit orders for non-existent power
        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "NONEXISTENT",
            "orders": ["A PAR - BUR"],
            "telegram_id": "error_user3"
        })
        assert resp.status_code == 404, f"Expected 404 Not Found, got {resp.status_code}: {resp.json()}"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_404_not_found_player(self, client):
        """Test 404 Not Found for non-existent player."""
        client.post("/users/persistent_register", json={"telegram_id": "error_user4", "full_name": "Error User 4"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        # Try to submit orders without joining game
        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "error_user4"
        })
        assert resp.status_code == 404, f"Expected 404 Not Found, got {resp.status_code}: {resp.json()}"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_409_conflict_power_taken(self, client):
        """Test 409 Conflict for power already taken."""
        client.post("/users/persistent_register", json={"telegram_id": "error_user5", "full_name": "Error User 5"})
        client.post("/users/persistent_register", json={"telegram_id": "error_user6", "full_name": "Error User 6"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        # User 5 joins as FRANCE
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "error_user5",
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        
        # User 6 tries to join as FRANCE (already taken)
        resp = client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "error_user6",
            "game_id": int(game_id),
            "power": "FRANCE"  # Already taken
        })
        assert resp.status_code in [400, 409], f"Expected 400 or 409, got {resp.status_code}: {resp.json()}"  # May be 400 or 409
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_401_unauthorized_no_token(self, client):
        """Test 401 Unauthorized for missing authentication."""
        # Try to access protected endpoint without token
        resp = client.get("/users/me/games")
        assert resp.status_code == 401, f"Expected 401 Unauthorized, got {resp.status_code}: {resp.json()}"


@pytest.mark.unit
@pytest.mark.integration
class TestErrorMessages:
    """Test that error messages are clear and helpful."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_error_message_game_not_found(self, client):
        """Test error message for game not found."""
        resp = client.get("/games/99999/state")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data or "message" in data
        error_msg = data.get("detail") or data.get("message", "")
        assert "not found" in error_msg.lower() or "game" in error_msg.lower()
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_error_message_unauthorized(self, client):
        """Test error message for unauthorized action."""
        client.post("/users/persistent_register", json={"telegram_id": "error_user7", "full_name": "Error User 7"})
        client.post("/users/persistent_register", json={"telegram_id": "error_user8", "full_name": "Error User 8"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "error_user7",
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        
        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "error_user8"  # Not authorized
        })
        assert resp.status_code == 403
        data = resp.json()
        error_msg = data.get("detail") or data.get("message", "")
        assert "not authorized" in error_msg.lower() or "unauthorized" in error_msg.lower()
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_error_message_invalid_order(self, client):
        """Test error message for invalid order."""
        client.post("/users/persistent_register", json={"telegram_id": "error_user9", "full_name": "Error User 9"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "error_user9",
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        
        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["INVALID ORDER FORMAT"],
            "telegram_id": "error_user9"
        })
        assert resp.status_code == 200  # Returns results with success=False
        data = resp.json()
        assert "results" in data
        # Check that error message is present
        for result in data["results"]:
            if not result.get("success"):
                assert "error" in result or "message" in result


@pytest.mark.unit
@pytest.mark.integration
class TestInvalidInputHandling:
    """Test that invalid inputs are handled gracefully."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_invalid_game_id_format(self, client):
        """Test handling of invalid game ID format."""
        # Try with non-numeric game ID
        resp = client.get("/games/invalid_id/state")
        assert resp.status_code in [400, 404, 422], \
            f"Expected 400, 404, or 422, got {resp.status_code}: {resp.json()}"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_invalid_power_name(self, client):
        """Test handling of invalid power name."""
        client.post("/users/persistent_register", json={"telegram_id": "error_user10", "full_name": "Error User 10"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        # Try to join with invalid power name
        resp = client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "error_user10",
            "game_id": int(game_id),
            "power": "INVALID_POWER"
        })
        assert resp.status_code in [400, 404], \
            f"Expected 400 or 404, got {resp.status_code}: {resp.json()}"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_empty_orders_list(self, client):
        """Test handling of empty orders list."""
        client.post("/users/persistent_register", json={"telegram_id": "error_user11", "full_name": "Error User 11"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "error_user11",
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        
        # Submit empty orders list (should clear orders)
        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": [],
            "telegram_id": "error_user11"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.json()}"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_malformed_json(self, client):
        """Test handling of malformed JSON."""
        # Send malformed JSON
        resp = client.post(
            "/games/create",
            data="invalid json{",
            headers={"Content-Type": "application/json"}
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"


@pytest.mark.unit
class TestEngineErrorHandling:
    """Test error handling in game engine."""
    
    def test_invalid_order_raises_value_error(self):
        """Test that invalid orders raise ValueError."""
        from engine.game import Game
        
        game = Game('standard')
        game.add_player('FRANCE')
        
        # Try to set invalid order
        with pytest.raises(ValueError):
            game.set_orders('FRANCE', ['INVALID ORDER'])
    
    def test_order_for_nonexistent_unit_raises_error(self):
        """Test that orders for non-existent units raise error."""
        from engine.game import Game
        
        game = Game('standard')
        game.add_player('FRANCE')
        
        # Remove all units to test non-existent unit
        game.game_state.powers['FRANCE'].units = []
        
        # Try to order unit that doesn't exist
        with pytest.raises(ValueError):
            game.set_orders('FRANCE', ['A PAR - BUR'])  # No unit in PAR
    
    def test_order_in_wrong_phase_raises_error(self):
        """Test that orders in wrong phase raise error."""
        from engine.game import Game
        
        game = Game('standard')
        game.add_player('FRANCE')
        game.game_state.powers['FRANCE'].units = [
            game.game_state.powers['FRANCE'].units[0] if game.game_state.powers['FRANCE'].units else None
        ]
        
        # Set to Builds phase
        game.phase = "Builds"
        game._update_phase_code()
        
        # Try to submit movement order in Builds phase
        if game.game_state.powers['FRANCE'].units:
            with pytest.raises(ValueError, match="not valid for phase|Builds"):
                game.set_orders('FRANCE', ['A PAR - BUR'])
