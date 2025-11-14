"""
Unit tests for admin API routes.

Tests administrative endpoints for managing games, users, caches, and system status.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from server.api import app, ADMIN_TOKEN
from server.api.shared import db_service, server
from tests.conftest import _get_db_url


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.mark.unit
class TestAdminDeleteGames:
    """Test admin delete all games endpoint."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_delete_all_games_success(self, client):
        """Test successful deletion of all games."""
        # Create some games first
        client.post("/games/create", json={"map_name": "standard"})
        client.post("/games/create", json={"map_name": "standard"})
        
        # Delete all games
        resp = client.post("/admin/delete_all_games")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "deleted_count" in data


@pytest.mark.unit
class TestAdminCounts:
    """Test admin count endpoints."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_games_count(self, client):
        """Test getting games count."""
        resp = client.get("/admin/games_count")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert isinstance(data["count"], int)
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_users_count(self, client):
        """Test getting users count."""
        resp = client.get("/admin/users_count")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert isinstance(data["count"], int)


@pytest.mark.unit
class TestAdminCacheManagement:
    """Test admin cache management endpoints."""
    
    def test_get_map_cache_stats(self, client):
        """Test getting map cache statistics."""
        resp = client.get("/admin/map_cache_stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "cache_stats" in data
    
    def test_clear_map_cache(self, client):
        """Test clearing map cache."""
        resp = client.post("/admin/clear_map_cache")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
    
    def test_get_response_cache_stats(self, client):
        """Test getting response cache statistics."""
        resp = client.get("/admin/response_cache_stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "cache_stats" in data
    
    def test_clear_response_cache(self, client):
        """Test clearing response cache."""
        resp = client.post("/admin/clear_response_cache")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_invalidate_game_cache(self, client):
        """Test invalidating cache for specific game."""
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        # Invalidate cache
        resp = client.post(f"/admin/invalidate_cache/{game_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


@pytest.mark.unit
class TestAdminMapManagement:
    """Test admin map management endpoints."""
    
    def test_preload_maps(self, client):
        """Test preloading common maps."""
        resp = client.post("/admin/preload_maps")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_cleanup_old_maps(self, client):
        """Test cleaning up old map images."""
        resp = client.post("/admin/cleanup_old_maps")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "cleaned_count" in data


@pytest.mark.unit
class TestAdminConnectionPool:
    """Test admin connection pool endpoints."""
    
    def test_get_connection_pool_status(self, client):
        """Test getting connection pool status."""
        resp = client.get("/admin/connection_pool_status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
    
    def test_reset_connection_pool(self, client):
        """Test resetting connection pool."""
        resp = client.post("/admin/connection_pool_reset")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


@pytest.mark.unit
class TestAdminMarkPlayerInactive:
    """Test admin mark player inactive endpoint."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_mark_player_inactive_success(self, client):
        """Test successfully marking player inactive."""
        # Setup: register user and join game
        client.post("/users/persistent_register", json={"telegram_id": "inactive_user", "full_name": "Inactive"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = int(game_resp.json()["game_id"])
        client.post(f"/games/{game_id}/join", json={"telegram_id": "inactive_user", "game_id": game_id, "power": "FRANCE"})
        
        # Mark inactive
        resp = client.post(f"/games/{game_id}/players/FRANCE/mark_inactive", json={"admin_token": ADMIN_TOKEN})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_mark_player_inactive_invalid_token(self, client):
        """Test marking player inactive with invalid token."""
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = int(game_resp.json()["game_id"])
        
        resp = client.post(f"/games/{game_id}/players/FRANCE/mark_inactive", json={"admin_token": "invalid"})
        assert resp.status_code == 403

