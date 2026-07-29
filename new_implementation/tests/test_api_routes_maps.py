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

BOT_SECRET = "test_bot_secret_for_tests"


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
class TestGetMapPreviewPng:
    """Test GET /maps/{map_name}/preview.png -- the unit-less sample board used by
    the bot's "View Sample Map" button."""

    def test_preview_standard_returns_real_png(self, client):
        resp = client.get("/maps/standard/preview.png")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"

    def test_preview_unknown_map_name_is_404(self, client):
        resp = client.get("/maps/not-a-real-map/preview.png")
        assert resp.status_code == 404

    def test_preview_second_request_hits_renderer_byte_cache(self, client):
        """The route calls ``Map.render_board_png`` on every request, but that
        function's own ``MapCache`` (keyed by svg_path/units/phase_info, which are
        fixed here) should short-circuit the actual SVG->PNG conversion on repeat
        calls for the same map name -- no second caching layer needed in the route."""
        from rendering import map as map_module

        # Warm the cache first, outside the patch, so this test doesn't depend on
        # whether an earlier test already populated it.
        warm = client.get("/maps/standard/preview.png")
        assert warm.status_code == 200

        with patch.object(map_module, "cairosvg") as mock_cairosvg:
            resp = client.get("/maps/standard/preview.png")

        assert resp.status_code == 200
        assert resp.content == warm.content
        mock_cairosvg.svg2png.assert_not_called()


@pytest.mark.unit
class TestGetGameOrdersMapPng:
    """Test GET /games/{game_id}/map/orders -- streams the orders-overlay PNG
    as bytes (E1c), unlike the pre-existing POST .../generate_map/orders which
    only returns a server-filesystem path unreachable from a browser."""

    def test_orders_map_game_not_found(self, client):
        resp = client.get("/games/nonexistent/map/orders")
        assert resp.status_code == 404

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_orders_map_returns_real_png_with_no_orders_submitted(self, client):
        """Renders a plain board when no orders have been submitted yet, same
        as the POST variant."""
        headers = _register_and_login(client, "ordersmap")
        game_id = _create_game(client, headers)
        resp = client.get(f"/games/{game_id}/map/orders")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_orders_map_returns_real_png_with_pending_orders(self, client):
        """With a pending order submitted, the endpoint still renders bytes
        (the arrow-overlay path, not the plain-board fallback)."""
        headers = _register_and_login(client, "ordersmap2")
        game_id = _create_game(client, headers)
        join = client.post(
            f"/games/{game_id}/join",
            json={"game_id": int(game_id), "power": "FRANCE"},
            headers=headers,
        )
        assert join.status_code == 200, join.text
        set_resp = client.post(
            "/games/set_orders",
            json={"game_id": game_id, "power": "FRANCE", "orders": ["A PAR H"]},
            headers=headers,
        )
        assert set_resp.status_code == 200, set_resp.text

        resp = client.get(f"/games/{game_id}/map/orders")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.unit
class TestGetGameResolutionMapPng:
    """Test GET /games/{game_id}/map/resolution -- streams the
    resolution-overlay PNG as bytes (E1c)."""

    def test_resolution_map_game_not_found(self, client):
        resp = client.get("/games/nonexistent/map/resolution")
        assert resp.status_code == 404

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_resolution_map_falls_back_to_plain_board_before_any_turn(self, client):
        """No turn processed yet -> no last_resolution -> plain board, not 500."""
        headers = _register_and_login(client, "resmap")
        game_id = _create_game(client, headers)
        resp = client.get(f"/games/{game_id}/map/resolution")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_resolution_map_after_process_turn(self, client):
        """After a turn is processed, renders the resolution-arrow overlay."""
        headers = _register_and_login(client, "resmap2")
        game_id = _create_game(client, headers)
        # process_turn now requires bot-secret/admin-token/membership (E1d) --
        # the game creator hasn't joined as a power, so use the bot-secret path.
        process_resp = client.post(
            f"/games/{game_id}/process_turn", headers={"X-Bot-Secret": BOT_SECRET}
        )
        assert process_resp.status_code == 200, process_resp.text

        resp = client.get(f"/games/{game_id}/map/resolution")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


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

