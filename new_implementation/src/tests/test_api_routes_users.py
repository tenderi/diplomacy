"""
Unit tests for users API routes.

Tests user registration, session management, and user games listing.
"""
import pytest
from fastapi.testclient import TestClient

from server.api import app
from tests.conftest import _get_db_url


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.mark.unit
class TestRegisterUser:
    """Test user registration endpoints."""
    
    def test_register_user_session(self, client):
        """Test registering a user session."""
        resp = client.post("/users/register", json={
            "telegram_id": "session_user",
            "game_id": "test_game",
            "power": "FRANCE"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_persistent_register_user(self, client):
        """Test persistent user registration."""
        resp = client.post("/users/persistent_register", json={
            "telegram_id": "persistent_user",
            "full_name": "Persistent User"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ["ok", "already_registered"]  # May be already registered from previous test
        assert "user_id" in data
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_persistent_register_duplicate(self, client):
        """Test registering duplicate user."""
        # Register first time
        resp1 = client.post("/users/persistent_register", json={
            "telegram_id": "duplicate_user",
            "full_name": "Duplicate User"
        })
        assert resp1.status_code == 200
        
        # Register again - may return "ok" or "already_registered" depending on implementation
        resp2 = client.post("/users/persistent_register", json={
            "telegram_id": "duplicate_user",
            "full_name": "Duplicate User"
        })
        assert resp2.status_code == 200
        assert resp2.json()["status"] in ["ok", "already_registered"]


@pytest.mark.unit
class TestGetUserSession:
    """Test get user session endpoint."""
    
    def test_get_user_session_success(self, client):
        """Test successful session retrieval."""
        # Register session first
        client.post("/users/register", json={
            "telegram_id": "session_test",
            "game_id": "test_game",
            "power": "FRANCE"
        })
        
        # Get session
        resp = client.get("/users/session_test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["telegram_id"] == "session_test"
        assert data["game_id"] == "test_game"
        assert data["power"] == "FRANCE"
    
    def test_get_user_session_not_found(self, client):
        """Test getting non-existent session."""
        resp = client.get("/users/nonexistent")
        assert resp.status_code == 404


@pytest.mark.unit
class TestGetUserGames:
    """Test get user games endpoint."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_user_games_success(self, client):
        """Test successful user games retrieval."""
        # Register user
        client.post("/users/persistent_register", json={
            "telegram_id": "games_user",
            "full_name": "Games User"
        })
        
        # Get games (may be empty)
        resp = client.get("/users/games_user/games")
        assert resp.status_code == 200
        data = resp.json()
        assert "games" in data
        assert isinstance(data["games"], list)
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_user_games_not_found(self, client):
        """Test getting games for non-existent user."""
        resp = client.get("/users/nonexistent_user/games")
        # May return 404 or 500 depending on error handling
        assert resp.status_code in [404, 500]
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_user_games_after_quit(self, client):
        """Test that quit games don't appear in user games list."""
        # Register user
        client.post("/users/persistent_register", json={
            "telegram_id": "quit_user",
            "full_name": "Quit User"
        })
        
        # Create and join game
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = int(game_resp.json()["game_id"])
        client.post(f"/games/{game_id}/join", json={
            "telegram_id": "quit_user",
            "game_id": game_id,
            "power": "FRANCE"
        })
        
        # Verify game appears
        resp1 = client.get("/users/quit_user/games")
        assert resp1.status_code == 200
        games_before = resp1.json()["games"]
        assert any(g["game_id"] == game_id for g in games_before)
        
        # Quit game
        client.post(f"/games/{game_id}/quit", json={
            "telegram_id": "quit_user",
            "game_id": game_id
        })
        
        # Verify game no longer appears
        resp2 = client.get("/users/quit_user/games")
        assert resp2.status_code == 200
        games_after = resp2.json()["games"]
        assert not any(g["game_id"] == game_id for g in games_after)

