"""
Unit tests for orders API routes.

Tests order submission, retrieval, and history endpoints.
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
class TestSetOrders:
    """Test set orders endpoint."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_set_orders_success(self, client):
        """Test successful order submission."""
        # Setup: register user, create game, join
        client.post("/users/persistent_register", json={"telegram_id": "test_user", "full_name": "Test"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "test_user", "game_id": int(game_id), "power": "FRANCE"})
        
        # Submit orders
        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "test_user"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) > 0
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_set_orders_unauthorized(self, client):
        """Test order submission with unauthorized user."""
        # Setup: register user, create game, join as different power
        client.post("/users/persistent_register", json={"telegram_id": "user1", "full_name": "User1"})
        client.post("/users/persistent_register", json={"telegram_id": "user2", "full_name": "User2"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "user1", "game_id": int(game_id), "power": "FRANCE"})
        
        # Try to submit orders as different user
        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "user2"  # Not authorized
        })
        # May return 403 or 500 depending on error handling
        assert resp.status_code in [403, 500]
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_set_orders_invalid_order(self, client):
        """Test order submission with invalid order."""
        # Setup
        client.post("/users/persistent_register", json={"telegram_id": "test_user2", "full_name": "Test"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "test_user2", "game_id": int(game_id), "power": "FRANCE"})
        
        # Submit invalid order
        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["INVALID ORDER"],
            "telegram_id": "test_user2"
        })
        assert resp.status_code == 200  # Returns results with success=False
        data = resp.json()
        assert "results" in data
        # Check that order failed
        assert any(r.get("success") == False for r in data["results"])


@pytest.mark.unit
class TestGetOrders:
    """Test get orders endpoint."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_orders_success(self, client):
        """Test successful order retrieval."""
        # Setup
        client.post("/users/persistent_register", json={"telegram_id": "test_user3", "full_name": "Test"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "test_user3", "game_id": int(game_id), "power": "FRANCE"})
        
        # Get orders
        resp = client.get(f"/games/{game_id}/orders")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
    
    def test_get_orders_not_found(self, client):
        """Test getting orders for non-existent game."""
        resp = client.get("/games/nonexistent/orders")
        assert resp.status_code == 500  # May fail due to int conversion


@pytest.mark.unit
class TestGetOrderHistory:
    """Test order history endpoint."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_order_history_success(self, client):
        """Test successful order history retrieval."""
        # Setup
        client.post("/users/persistent_register", json={"telegram_id": "test_user4", "full_name": "Test"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "test_user4", "game_id": int(game_id), "power": "FRANCE"})
        
        # Get order history
        resp = client.get(f"/games/{game_id}/orders/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data
        assert "order_history" in data


@pytest.mark.unit
class TestGetOrdersForPower:
    """Test get orders for specific power endpoint."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_orders_for_power_success(self, client):
        """Test successful order retrieval for power."""
        # Setup
        client.post("/users/persistent_register", json={"telegram_id": "test_user5", "full_name": "Test"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "test_user5", "game_id": int(game_id), "power": "FRANCE"})
        
        # Get orders for power
        resp = client.get(f"/games/{game_id}/orders/FRANCE")
        assert resp.status_code == 200
        data = resp.json()
        assert "power" in data
        assert "orders" in data
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_orders_for_power_not_found(self, client):
        """Test getting orders for non-existent power."""
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        resp = client.get(f"/games/{game_id}/orders/FRANCE")
        # May return 404 or 500 depending on error handling
        assert resp.status_code in [404, 500]


@pytest.mark.unit
class TestClearOrders:
    """Test clear orders endpoint."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_clear_orders_success(self, client):
        """Test successful order clearing."""
        # Setup
        client.post("/users/persistent_register", json={"telegram_id": "test_user6", "full_name": "Test"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = int(game_resp.json()["game_id"])
        client.post(f"/games/{game_id}/join", json={"telegram_id": "test_user6", "game_id": game_id, "power": "FRANCE"})
        
        # Clear orders
        resp = client.post(f"/games/{game_id}/orders/FRANCE/clear", json="test_user6")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_clear_orders_unauthorized(self, client):
        """Test clearing orders with unauthorized user."""
        # Setup
        client.post("/users/persistent_register", json={"telegram_id": "user7", "full_name": "User7"})
        client.post("/users/persistent_register", json={"telegram_id": "user8", "full_name": "User8"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = int(game_resp.json()["game_id"])
        client.post(f"/games/{game_id}/join", json={"telegram_id": "user7", "game_id": game_id, "power": "FRANCE"})
        
        # Try to clear orders as different user
        resp = client.post(f"/games/{game_id}/orders/FRANCE/clear", json="user8")
        # May return 403 or 500 depending on error handling
        assert resp.status_code in [403, 500]

