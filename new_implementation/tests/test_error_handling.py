"""
Comprehensive tests for error handling and HTTP status codes.

Tests that all error conditions return correct HTTP status codes
and that error messages are clear and helpful.
"""
import time
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from server.api import app
from tests.conftest import _get_db_url


BOT_SECRET = "test_bot_secret_for_tests"


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def _register_and_login(client, prefix="err"):
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
@pytest.mark.integration
class TestHTTPStatusCodes:
    """Test that correct HTTP status codes are returned for various scenarios."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_400_bad_request_missing_fields(self, client):
        """Test 400 Bad Request for missing required fields."""
        resp = client.post("/games/set_orders", json={
            "game_id": "123"
        })
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.json()}"

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_403_forbidden_unauthorized_action(self, client):
        """Test 403 Forbidden for unauthorized actions."""
        headers = _register_and_login(client, "err403")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "error_user1", "full_name": "Error User 1", "bot_secret": BOT_SECRET})
        client.post("/users/persistent_register", json={"telegram_id": "error_user2", "full_name": "Error User 2", "bot_secret": BOT_SECRET})
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "error_user1",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "FRANCE"
        })

        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "error_user2",
            "bot_secret": BOT_SECRET
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
        headers = _register_and_login(client, "err404p")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "error_user3", "full_name": "Error User 3", "bot_secret": BOT_SECRET})

        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "NONEXISTENT",
            "orders": ["A PAR - BUR"],
            "telegram_id": "error_user3",
            "bot_secret": BOT_SECRET
        })
        assert resp.status_code == 404, f"Expected 404 Not Found, got {resp.status_code}: {resp.json()}"

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_404_not_found_player(self, client):
        """Test 404 Not Found for non-existent player."""
        headers = _register_and_login(client, "err404pl")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "error_user4", "full_name": "Error User 4", "bot_secret": BOT_SECRET})

        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "error_user4",
            "bot_secret": BOT_SECRET
        })
        assert resp.status_code == 404, f"Expected 404 Not Found, got {resp.status_code}: {resp.json()}"

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_409_conflict_power_taken(self, client):
        """Test 409 Conflict for power already taken."""
        headers = _register_and_login(client, "err409")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "error_user5", "full_name": "Error User 5", "bot_secret": BOT_SECRET})
        client.post("/users/persistent_register", json={"telegram_id": "error_user6", "full_name": "Error User 6", "bot_secret": BOT_SECRET})
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "error_user5",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "FRANCE"
        })

        resp = client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "error_user6",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        assert resp.status_code in [400, 409], f"Expected 400 or 409, got {resp.status_code}: {resp.json()}"

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_401_unauthorized_no_token(self, client):
        """Test 401 Unauthorized for missing authentication."""
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
        headers = _register_and_login(client, "errmsg7")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "error_user7", "full_name": "Error User 7", "bot_secret": BOT_SECRET})
        client.post("/users/persistent_register", json={"telegram_id": "error_user8", "full_name": "Error User 8", "bot_secret": BOT_SECRET})
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "error_user7",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "FRANCE"
        })

        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "error_user8",
            "bot_secret": BOT_SECRET
        })
        assert resp.status_code == 403
        data = resp.json()
        error_msg = data.get("detail") or data.get("message", "")
        assert "not authorized" in error_msg.lower() or "unauthorized" in error_msg.lower()

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_error_message_invalid_order(self, client):
        """Test error message for invalid order."""
        headers = _register_and_login(client, "errmsg9")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "error_user9", "full_name": "Error User 9", "bot_secret": BOT_SECRET})
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "error_user9",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "FRANCE"
        })

        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["INVALID ORDER FORMAT"],
            "telegram_id": "error_user9",
            "bot_secret": BOT_SECRET
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
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
        resp = client.get("/games/invalid_id/state")
        assert resp.status_code in [400, 404, 422], \
            f"Expected 400, 404, or 422, got {resp.status_code}: {resp.json()}"

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_invalid_power_name(self, client):
        """Test handling of invalid power name."""
        headers = _register_and_login(client, "errinv10")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "error_user10", "full_name": "Error User 10", "bot_secret": BOT_SECRET})

        resp = client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "error_user10",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "INVALID_POWER"
        })
        assert resp.status_code in [400, 404], \
            f"Expected 400 or 404, got {resp.status_code}: {resp.json()}"

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_empty_orders_list(self, client):
        """Test handling of empty orders list."""
        headers = _register_and_login(client, "errempty11")
        game_id = _create_game(client, headers)
        client.post("/users/persistent_register", json={"telegram_id": "error_user11", "full_name": "Error User 11", "bot_secret": BOT_SECRET})
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "error_user11",
            "bot_secret": BOT_SECRET,
            "game_id": int(game_id),
            "power": "FRANCE"
        })

        resp = client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": [],
            "telegram_id": "error_user11",
            "bot_secret": BOT_SECRET
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.json()}"

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_malformed_json(self, client):
        """Test handling of malformed JSON."""
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

        with pytest.raises(ValueError):
            game.set_orders('FRANCE', ['INVALID ORDER'])

    def test_order_for_nonexistent_unit_raises_error(self):
        """Test that orders for non-existent units raise error."""
        from engine.game import Game

        game = Game('standard')
        game.add_player('FRANCE')
        game.game_state.powers['FRANCE'].units = []

        with pytest.raises(ValueError):
            game.set_orders('FRANCE', ['A PAR - BUR'])

    def test_order_in_wrong_phase_raises_error(self):
        """Test that orders in wrong phase raise error."""
        from engine.game import Game

        game = Game('standard')
        game.add_player('FRANCE')
        game.game_state.powers['FRANCE'].units = [
            game.game_state.powers['FRANCE'].units[0] if game.game_state.powers['FRANCE'].units else None
        ]

        game.phase = "Builds"
        game._update_phase_code()

        if game.game_state.powers['FRANCE'].units:
            with pytest.raises(ValueError, match="not valid for phase|Builds"):
                game.set_orders('FRANCE', ['A PAR - BUR'])
