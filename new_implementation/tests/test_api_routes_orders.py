"""
Unit tests for orders API routes.

Tests order submission, retrieval, and history endpoints.
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


def _register_and_login(client, prefix="orders"):
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
class TestSetOrders:
    """Test set orders endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_set_orders_success(self, client):
        """Test successful order submission."""
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "test_user", "full_name": "Test"})
        headers = _register_and_login(client, "ord_set1")
        game_id = _create_game(client, headers)
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "test_user", "bot_secret": BOT_SECRET, "game_id": int(game_id), "power": "FRANCE"})

        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "test_user",
            "bot_secret": BOT_SECRET
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) > 0

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_set_orders_unauthorized(self, client):
        """Test order submission with unauthorized user."""
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "user1", "full_name": "User1"})
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "user2", "full_name": "User2"})
        headers = _register_and_login(client, "ord_unauth")
        game_id = _create_game(client, headers)
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "user1", "bot_secret": BOT_SECRET, "game_id": int(game_id), "power": "FRANCE"})

        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "user2",
            "bot_secret": BOT_SECRET
        })
        assert resp.status_code in [403, 500]

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_set_orders_invalid_order(self, client):
        """Test order submission with invalid order."""
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "test_user2", "full_name": "Test"})
        headers = _register_and_login(client, "ord_inv")
        game_id = _create_game(client, headers)
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "test_user2", "bot_secret": BOT_SECRET, "game_id": int(game_id), "power": "FRANCE"})

        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["INVALID ORDER"],
            "telegram_id": "test_user2",
            "bot_secret": BOT_SECRET
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert any(r.get("success") is False for r in data["results"])


@pytest.mark.unit
class TestGetOrders:
    """Test get orders endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_orders_success(self, client):
        """Test successful order retrieval."""
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "test_user3", "full_name": "Test"})
        headers = _register_and_login(client, "ord_get3")
        game_id = _create_game(client, headers)
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "test_user3", "bot_secret": BOT_SECRET, "game_id": int(game_id), "power": "FRANCE"})

        resp = client.get(f"/games/{game_id}/orders")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_orders_not_found(self, client):
        """Test getting orders for non-existent game."""
        resp = client.get("/games/nonexistent/orders")
        assert resp.status_code == 500


@pytest.mark.unit
class TestGetOrderHistory:
    """Test order history endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_order_history_success(self, client):
        """Test successful order history retrieval."""
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "test_user4", "full_name": "Test"})
        headers = _register_and_login(client, "ord_hist4")
        game_id = _create_game(client, headers)
        client.post(f"/games/{int(game_id)}/join", json={"telegram_id": "test_user4", "bot_secret": BOT_SECRET, "game_id": int(game_id), "power": "FRANCE"})

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
        """Test successful order retrieval for power (Bearer auth)."""
        headers = _register_and_login(client, "ord_power5")
        game_id = _create_game(client, headers)
        client.post(f"/games/{int(game_id)}/join", json={"game_id": int(game_id), "power": "FRANCE"}, headers=headers)

        resp = client.get(f"/games/{game_id}/orders/FRANCE", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "power" in data
        assert "orders" in data

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_orders_for_power_not_found(self, client):
        """Test getting orders for non-existent power."""
        headers = _register_and_login(client, "ord_notfound")
        game_id = _create_game(client, headers)

        resp = client.get(f"/games/{game_id}/orders/FRANCE")
        assert resp.status_code in [404, 500]


@pytest.mark.unit
class TestClearOrders:
    """Test clear orders endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_clear_orders_success(self, client):
        """Test successful order clearing."""
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "test_user6", "full_name": "Test"})
        headers = _register_and_login(client, "ord_clear6")
        game_id = _create_game(client, headers)
        game_id_int = int(game_id)
        client.post(f"/games/{game_id_int}/join", json={"telegram_id": "test_user6", "bot_secret": BOT_SECRET, "game_id": game_id_int, "power": "FRANCE"})

        resp = client.post(f"/games/{game_id_int}/orders/FRANCE/clear", json={"telegram_id": "test_user6", "bot_secret": BOT_SECRET})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_clear_orders_unauthorized(self, client):
        """Test clearing orders with unauthorized user."""
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "user7", "full_name": "User7"})
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": "user8", "full_name": "User8"})
        headers = _register_and_login(client, "ord_clrunauth")
        game_id = _create_game(client, headers)
        game_id_int = int(game_id)
        client.post(f"/games/{game_id_int}/join", json={"telegram_id": "user7", "bot_secret": BOT_SECRET, "game_id": game_id_int, "power": "FRANCE"})

        resp = client.post(f"/games/{game_id_int}/orders/FRANCE/clear", json={"telegram_id": "user8", "bot_secret": BOT_SECRET})
        assert resp.status_code in [403, 500]
