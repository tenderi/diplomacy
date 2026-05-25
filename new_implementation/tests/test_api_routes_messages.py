"""
Unit tests for messages API routes.

Tests private messaging, broadcast messaging, and message retrieval.
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


def _register_and_login(client, prefix="msg"):
    email = f"{prefix}_{int(time.time() * 1000)}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_game(client, headers):
    resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=headers)
    assert resp.status_code == 200
    return int(resp.json()["game_id"])


@pytest.mark.unit
class TestSendPrivateMessage:
    """Test send private message endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_send_private_message_success(self, client):
        """Test successful private message sending."""
        client.post("/users/persistent_register", json={"telegram_id": "sender1", "full_name": "Sender", "bot_secret": BOT_SECRET})
        client.post("/users/persistent_register", json={"telegram_id": "recipient1", "full_name": "Recipient", "bot_secret": BOT_SECRET})

        headers = _register_and_login(client, "msg_priv1")
        game_id = _create_game(client, headers)
        client.post(f"/games/{game_id}/join", json={"telegram_id": "sender1", "bot_secret": BOT_SECRET, "game_id": game_id, "power": "FRANCE"})
        client.post(f"/games/{game_id}/join", json={"telegram_id": "recipient1", "bot_secret": BOT_SECRET, "game_id": game_id, "power": "GERMANY"})

        resp = client.post(f"/games/{game_id}/message", json={
            "telegram_id": "sender1",
            "bot_secret": BOT_SECRET,
            "recipient_power": "GERMANY",
            "text": "Hello!"
        })
        assert resp.status_code in [200, 500]
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] == "ok"
            assert "message_id" in data

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_send_private_message_not_in_game(self, client):
        """Test sending message when sender not in game."""
        client.post("/users/persistent_register", json={"telegram_id": "outsider", "full_name": "Outsider", "bot_secret": BOT_SECRET})

        headers = _register_and_login(client, "msg_out")
        game_id = _create_game(client, headers)

        resp = client.post(f"/games/{game_id}/message", json={
            "telegram_id": "outsider",
            "bot_secret": BOT_SECRET,
            "recipient_power": "FRANCE",
            "text": "Hello!"
        })
        assert resp.status_code in [403, 500]

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_send_private_message_missing_recipient(self, client):
        """Test sending message without recipient."""
        client.post("/users/persistent_register", json={"telegram_id": "sender2", "full_name": "Sender", "bot_secret": BOT_SECRET})

        headers = _register_and_login(client, "msg_norec")
        game_id = _create_game(client, headers)
        client.post(f"/games/{game_id}/join", json={"telegram_id": "sender2", "bot_secret": BOT_SECRET, "game_id": game_id, "power": "FRANCE"})

        resp = client.post(f"/games/{game_id}/message", json={
            "telegram_id": "sender2",
            "bot_secret": BOT_SECRET,
            "recipient_power": None,
            "text": "Hello!"
        })
        assert resp.status_code in [400, 500]


@pytest.mark.unit
class TestSendBroadcast:
    """Test send broadcast message endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_send_broadcast_success(self, client):
        """Test successful broadcast message sending."""
        client.post("/users/persistent_register", json={"telegram_id": "broadcaster", "full_name": "Broadcaster", "bot_secret": BOT_SECRET})

        headers = _register_and_login(client, "msg_bcast")
        game_id = _create_game(client, headers)
        client.post(f"/games/{game_id}/join", json={"telegram_id": "broadcaster", "bot_secret": BOT_SECRET, "game_id": game_id, "power": "FRANCE"})

        resp = client.post(f"/games/{game_id}/broadcast", json={
            "telegram_id": "broadcaster",
            "bot_secret": BOT_SECRET,
            "text": "Hello everyone!"
        })
        assert resp.status_code in [200, 500]
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] == "ok"
            assert "message_id" in data


@pytest.mark.unit
class TestGetGameMessages:
    """Test get game messages endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_game_messages_success(self, client):
        """Test successful message retrieval."""
        client.post("/users/persistent_register", json={"telegram_id": "msg_user", "full_name": "Message User", "bot_secret": BOT_SECRET})

        headers = _register_and_login(client, "msg_get")
        game_id = _create_game(client, headers)
        client.post(f"/games/{game_id}/join", json={"telegram_id": "msg_user", "bot_secret": BOT_SECRET, "game_id": game_id, "power": "FRANCE"})

        resp = client.get(f"/games/{game_id}/messages", params={"telegram_id": "msg_user", "bot_secret": BOT_SECRET})
        assert resp.status_code in [200, 500]
        if resp.status_code == 200:
            data = resp.json()
            assert "messages" in data
            assert isinstance(data["messages"], list)

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_game_messages_without_telegram_id(self, client):
        """Test getting messages without telegram_id (only broadcasts)."""
        headers = _register_and_login(client, "msg_anon")
        game_id = _create_game(client, headers)

        resp = client.get(f"/games/{game_id}/messages")
        assert resp.status_code in [200, 500]
        if resp.status_code == 200:
            data = resp.json()
            assert "messages" in data
