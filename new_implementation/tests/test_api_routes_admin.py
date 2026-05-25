"""
Unit tests for admin API routes.

Tests administrative endpoints for managing games, users, caches, and system status.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from server.api import app, ADMIN_TOKEN
from server.api.shared import db_service, server, BOT_SECRET
from tests.conftest import _get_db_url


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def admin_headers():
    """Admin auth headers."""
    return {"X-Admin-Token": ADMIN_TOKEN}


@pytest.fixture
def bot_headers():
    """Bot auth headers (for game creation etc.)."""
    secret = BOT_SECRET or "test-bot-secret"
    return {"X-Bot-Secret": secret}


@pytest.mark.unit
class TestAdminDeleteGames:
    """Test admin delete all games endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_delete_all_games_success(self, client, admin_headers, bot_headers):
        """Test successful deletion of all games."""
        # Create some games first
        client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=bot_headers)
        client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=bot_headers)

        # Delete all games
        resp = client.post("/admin/delete_all_games", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "deleted_count" in data


@pytest.mark.unit
class TestAdminCounts:
    """Test admin count endpoints."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_games_count(self, client, admin_headers):
        """Test getting games count."""
        resp = client.get("/admin/games_count", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert isinstance(data["count"], int)

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_users_count(self, client, admin_headers):
        """Test getting users count."""
        resp = client.get("/admin/users_count", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert isinstance(data["count"], int)


@pytest.mark.unit
class TestAdminCacheManagement:
    """Test admin cache management endpoints."""

    def test_get_map_cache_stats(self, client, admin_headers):
        """Test getting map cache statistics."""
        resp = client.get("/admin/map_cache_stats", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "cache_stats" in data

    def test_clear_map_cache(self, client, admin_headers):
        """Test clearing map cache."""
        resp = client.post("/admin/clear_map_cache", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_get_response_cache_stats(self, client, admin_headers):
        """Test getting response cache statistics."""
        resp = client.get("/admin/response_cache_stats", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "cache_stats" in data

    def test_clear_response_cache(self, client, admin_headers):
        """Test clearing response cache."""
        resp = client.post("/admin/clear_response_cache", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_invalidate_game_cache(self, client, admin_headers, bot_headers):
        """Test invalidating cache for specific game."""
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=bot_headers)
        game_id = game_resp.json()["game_id"]

        resp = client.post(f"/admin/invalidate_cache/{game_id}", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


@pytest.mark.unit
class TestAdminMapManagement:
    """Test admin map management endpoints."""

    def test_preload_maps(self, client, admin_headers):
        """Test preloading common maps."""
        resp = client.post("/admin/preload_maps", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_cleanup_old_maps(self, client, admin_headers):
        """Test cleaning up old map images."""
        resp = client.post("/admin/cleanup_old_maps", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "cleaned_count" in data


@pytest.mark.unit
class TestAdminConnectionPool:
    """Test admin connection pool endpoints."""

    def test_get_connection_pool_status(self, client, admin_headers):
        """Test getting connection pool status."""
        resp = client.get("/admin/connection_pool_status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_reset_connection_pool(self, client, admin_headers):
        """Test resetting connection pool."""
        resp = client.post("/admin/connection_pool_reset", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


@pytest.mark.unit
class TestAdminMarkPlayerInactive:
    """Test admin mark player inactive endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_mark_player_inactive_success(self, client, admin_headers, bot_headers):
        """Test successfully marking player inactive."""
        client.post("/users/persistent_register", json={"telegram_id": "inactive_user", "full_name": "Inactive", "bot_secret": BOT_SECRET or ""})
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=bot_headers)
        game_id = int(game_resp.json()["game_id"])
        client.post(f"/games/{game_id}/join", json={"telegram_id": "inactive_user", "bot_secret": BOT_SECRET or "", "game_id": game_id, "power": "FRANCE"})

        resp = client.post(f"/games/{game_id}/players/FRANCE/mark_inactive", json={"admin_token": ADMIN_TOKEN})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_mark_player_inactive_invalid_token(self, client, bot_headers):
        """Test marking player inactive with invalid token."""
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=bot_headers)
        game_id = int(game_resp.json()["game_id"])

        resp = client.post(f"/games/{game_id}/players/FRANCE/mark_inactive", json={"admin_token": "invalid"})
        assert resp.status_code == 403


@pytest.mark.unit
class TestAdminUnauthorized:
    """Test that admin endpoints reject requests without valid token."""

    def test_no_token_rejected(self, client):
        """Admin endpoints must reject requests with no token (422 missing header)."""
        resp = client.get("/admin/map_cache_stats")
        assert resp.status_code == 422

    def test_wrong_token_rejected(self, client):
        """Admin endpoints must reject requests with wrong token (403)."""
        resp = client.get("/admin/map_cache_stats", headers={"X-Admin-Token": "wrong-token"})
        assert resp.status_code == 403
