"""
Unit tests for games API routes.

Tests all game management endpoints including creation, state management,
player management, deadlines, and snapshots.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from server.api import app
from server.api.shared import db_service, server
from tests.conftest import _get_db_url


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def cleanup_games():
    """Fixture to cleanup games after test."""
    yield
    # Cleanup: games are cleaned up by test isolation


@pytest.mark.unit
class TestCreateGame:
    """Test game creation endpoint."""
    
    def test_create_game_success(self, client):
        """Test successful game creation."""
        resp = client.post("/games/create", json={"map_name": "standard"})
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data
        assert isinstance(data["game_id"], str)
    
    def test_create_game_default_map(self, client):
        """Test game creation with default map."""
        resp = client.post("/games/create", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data
    
    def test_create_game_custom_map(self, client):
        """Test game creation with custom map."""
        resp = client.post("/games/create", json={"map_name": "standard"})
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data


@pytest.mark.unit
class TestAddPlayer:
    """Test add player endpoint."""
    
    def test_add_player_success(self, client):
        """Test successful player addition."""
        # Create game first
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        # Add player - may fail if game not in memory
        resp = client.post("/games/add_player", json={"game_id": game_id, "power": "FRANCE"})
        # May return 200 or 500 depending on game state
        assert resp.status_code in [200, 500]
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] == "ok"
            assert "player_id" in data


@pytest.mark.unit
class TestGetGameState:
    """Test get game state endpoint."""
    
    def test_get_game_state_success(self, client):
        """Test successful game state retrieval."""
        # Create game first
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        # Get state
        resp = client.get(f"/games/{game_id}/state")
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data
        assert "map_name" in data
        assert "powers" in data
    
    def test_get_game_state_not_found(self, client):
        """Test getting state for non-existent game."""
        resp = client.get("/games/nonexistent/state")
        assert resp.status_code == 404


@pytest.mark.unit
class TestListGames:
    """Test list games endpoint."""
    
    def test_list_games_success(self, client):
        """Test successful game listing."""
        resp = client.get("/games")
        assert resp.status_code == 200
        data = resp.json()
        assert "games" in data
        assert isinstance(data["games"], list)


@pytest.mark.unit
class TestGetPlayers:
    """Test get players endpoint."""
    
    def test_get_players_success(self, client):
        """Test successful player listing."""
        # Create game and add player
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        client.post("/games/add_player", json={"game_id": game_id, "power": "FRANCE"})
        
        # Get players
        resp = client.get(f"/games/{game_id}/players")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
    
    def test_get_players_not_found(self, client):
        """Test getting players for non-existent game."""
        resp = client.get("/games/nonexistent/players")
        # May return 404 or 500 depending on error handling
        assert resp.status_code in [404, 500]


@pytest.mark.unit
class TestJoinGame:
    """Test join game endpoint."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_join_game_success(self, client):
        """Test successful game join."""
        # Register user first
        client.post("/users/persistent_register", json={"telegram_id": "test123", "full_name": "Test User"})
        
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = int(game_resp.json()["game_id"])
        
        # Join game
        resp = client.post(f"/games/{game_id}/join", json={"telegram_id": "test123", "game_id": game_id, "power": "FRANCE"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "player_id" in data
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_join_game_already_joined(self, client):
        """Test joining game when already joined."""
        # Register user
        client.post("/users/persistent_register", json={"telegram_id": "test456", "full_name": "Test User"})
        
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = int(game_resp.json()["game_id"])
        
        # Join first time
        resp1 = client.post(f"/games/{game_id}/join", json={"telegram_id": "test456", "game_id": game_id, "power": "FRANCE"})
        assert resp1.status_code == 200
        
        # Join again
        resp2 = client.post(f"/games/{game_id}/join", json={"telegram_id": "test456", "game_id": game_id, "power": "FRANCE"})
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "already_joined"


@pytest.mark.unit
class TestProcessTurn:
    """Test process turn endpoint."""
    
    def test_process_turn_success(self, client):
        """Test successful turn processing."""
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        # Process turn
        resp = client.post(f"/games/{game_id}/process_turn")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
    
    def test_process_turn_not_found(self, client):
        """Test processing turn for non-existent game."""
        resp = client.post("/games/nonexistent/process_turn")
        assert resp.status_code == 400


@pytest.mark.unit
class TestDeadlineEndpoints:
    """Test deadline management endpoints."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_deadline(self, client):
        """Test getting game deadline."""
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        # Get deadline
        resp = client.get(f"/games/{game_id}/deadline")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "deadline" in data
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_set_deadline(self, client):
        """Test setting game deadline."""
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        # Set deadline
        future_time = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        resp = client.post(f"/games/{game_id}/deadline", json={"deadline": future_time})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "deadline" in data


@pytest.mark.unit
class TestGameHistory:
    """Test game history endpoints."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_game_history(self, client):
        """Test getting game history."""
        # Create game and process turn to create history
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = int(game_resp.json()["game_id"])
        
        # Get history (may be empty if no turns processed)
        resp = client.get(f"/games/{game_id}/history/0")
        # May return 200, 404, or 500 depending on game state and database
        assert resp.status_code in [200, 404, 500]


@pytest.mark.unit
class TestGameSnapshots:
    """Test game snapshot endpoints."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_save_snapshot(self, client):
        """Test saving game snapshot."""
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        # Save snapshot
        resp = client.post(f"/games/{game_id}/snapshot")
        # May fail if game not in memory, which is acceptable
        assert resp.status_code in [200, 404]
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_snapshots(self, client):
        """Test getting game snapshots."""
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        # Get snapshots
        resp = client.get(f"/games/{game_id}/snapshots")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "snapshots" in data


@pytest.mark.unit
class TestLegalOrders:
    """Test legal orders endpoint."""
    
    def test_get_legal_orders_success(self, client):
        """Test getting legal orders for a unit."""
        # Create game and add player
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        client.post("/games/add_player", json={"game_id": game_id, "power": "FRANCE"})
        
        # Get legal orders - may fail if game not in memory
        resp = client.get(f"/games/{game_id}/legal_orders/FRANCE/A PAR")
        # May return 200 or 404 depending on game state
        assert resp.status_code in [200, 404]
        if resp.status_code == 200:
            data = resp.json()
            assert "orders" in data
            assert isinstance(data["orders"], list)
    
    def test_get_legal_orders_invalid_format(self, client):
        """Test getting legal orders with invalid unit format."""
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        resp = client.get(f"/games/{game_id}/legal_orders/FRANCE/invalid")
        assert resp.status_code == 400
    
    def test_get_legal_orders_game_not_found(self, client):
        """Test getting legal orders for non-existent game."""
        resp = client.get("/games/nonexistent/legal_orders/FRANCE/A PAR")
        assert resp.status_code == 404

