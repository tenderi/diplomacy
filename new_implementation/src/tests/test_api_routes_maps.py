"""
Unit tests for maps API routes.

Tests map image generation endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from server.api import app
from tests.conftest import _get_db_url


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


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

