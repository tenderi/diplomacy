"""
Unit tests for maps API routes.

Tests map image generation endpoints.
"""
import time

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from server.api import app
from tests.conftest import _get_db_url


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def _register_and_login(client, prefix="maps"):
    """Register a user and return Bearer auth headers."""
    email = f"{prefix}_{int(time.time() * 1000)}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert reg.status_code == 200, f"Registration failed: {reg.text}"
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


def _create_game(client, headers):
    """Create a game with auth and return game_id."""
    resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=headers)
    assert resp.status_code == 200, f"Game creation failed: {resp.text}"
    return resp.json()["game_id"]


@pytest.mark.unit
class TestGenerateMap:
    """Test generate map endpoint."""
    
    def test_generate_map_game_not_found(self, client):
        """Test generating map for non-existent game."""
        resp = client.post("/games/nonexistent/generate_map")
        assert resp.status_code == 404
    
    @pytest.mark.skip(reason="Requires game in memory and map file")
    def test_generate_map_success(self, client):
        """Test successful map generation."""
        # This would require setting up a game in memory and map files
        # Skipping for now as it requires file system setup
        pass


@pytest.mark.unit
class TestGenerateOrdersMap:
    """Test generate orders map endpoint."""
    
    def test_generate_orders_map_game_not_found(self, client):
        """Test generating orders map for non-existent game."""
        resp = client.post("/games/nonexistent/generate_map/orders")
        assert resp.status_code == 404
    
    @pytest.mark.skip(reason="Requires game in memory and map file")
    def test_generate_orders_map_success(self, client):
        """Test successful orders map generation."""
        # This would require setting up a game in memory and map files
        pass


@pytest.mark.unit
class TestGenerateResolutionMap:
    """Test generate resolution map endpoint."""
    
    def test_generate_resolution_map_game_not_found(self, client):
        """Test generating resolution map for non-existent game."""
        resp = client.post("/games/nonexistent/generate_map/resolution")
        assert resp.status_code == 404
    
    @pytest.mark.skip(reason="Requires game in memory and map file")
    def test_generate_resolution_map_success(self, client):
        """Test successful resolution map generation."""
        # This would require setting up a game in memory and map files
        pass


@pytest.mark.unit
class TestGetGameMapHistoryPng:
    """Test GET /games/{game_id}/map/history/{turn} — renders a persisted snapshot."""

    def test_history_game_not_found(self, client):
        resp = client.get("/games/nonexistent/map/history/0")
        assert resp.status_code == 404

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_history_no_snapshot_for_turn(self, client):
        """A real game with no snapshot yet at that turn number -> 404."""
        headers = _register_and_login(client, "maphist_missing")
        game_id = _create_game(client, headers)
        resp = client.get(f"/games/{game_id}/map/history/999")
        assert resp.status_code == 404

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_history_renders_saved_snapshot(self, client):
        """A snapshot taken via POST /snapshot is fetchable as a PNG at its turn."""
        headers = _register_and_login(client, "maphist_ok")
        game_id = _create_game(client, headers)
        snap = client.post(f"/games/{int(game_id)}/snapshot")
        assert snap.status_code == 200, snap.text
        turn = snap.json()["turn"]

        resp = client.get(f"/games/{game_id}/map/history/{turn}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"

