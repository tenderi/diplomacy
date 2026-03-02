"""
Tests for spectator API endpoints.

POST/DELETE /games/{game_id}/spectate, GET .../spectators, GET .../observer_state.
Uses mocked db_service where needed.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from server.api import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_user():
    u = MagicMock()
    u.id = 42
    u.full_name = "Test User"
    u.telegram_id = None
    return u


@pytest.mark.unit
class TestSpectatorsAPI:
    """Test spectator join/leave, list, and observer_state."""

    @patch("server.api.routes.games.db_service")
    @patch("server.api.routes.games.resolve_user_or_telegram")
    def test_spectate_join_success(self, mock_resolve, mock_db, client, mock_user):
        mock_resolve.return_value = mock_user
        resp = client.post(
            "/games/g1/spectate",
            json={},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 200
        mock_db.add_spectator.assert_called_once_with(game_id="g1", user_id=42)

    @patch("server.api.routes.games.db_service")
    @patch("server.api.routes.games.resolve_user_or_telegram")
    def test_spectate_join_game_not_found(self, mock_resolve, mock_db, client, mock_user):
        mock_resolve.return_value = mock_user
        mock_db.add_spectator.side_effect = ValueError("Game g99 not found")
        resp = client.post(
            "/games/g99/spectate",
            json={},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 404

    @patch("server.api.routes.games.db_service")
    @patch("server.api.routes.games.resolve_user_or_telegram")
    def test_spectate_leave_success(self, mock_resolve, mock_db, client, mock_user):
        mock_resolve.return_value = mock_user
        resp = client.request(
            "DELETE",
            "/games/g1/spectate",
            json={},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 200
        mock_db.remove_spectator.assert_called_once_with(game_id="g1", user_id=42)

    @patch("server.api.routes.games.db_service")
    def test_get_spectators_success(self, mock_db, client):
        mock_db.get_spectators.return_value = [
            {"user_id": 1, "joined_at": "2025-03-02T12:00:00", "full_name": "Alice", "email": None},
        ]
        resp = client.get("/games/g1/spectators")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["game_id"] == "g1"
        assert len(data["spectators"]) == 1
        assert data["spectators"][0]["full_name"] == "Alice"

    @patch("server.api.routes.games.db_service")
    @patch("server.api.routes.games.server")
    def test_get_observer_state_returns_state_without_orders(self, mock_server, mock_db, client):
        from engine.data_models import GameState, PowerState, GameStatus, MapData
        from datetime import datetime, timezone

        map_data = MapData(
            map_name="standard",
            provinces={},
            supply_centers=[],
            home_supply_centers={},
            starting_positions={},
        )
        state = GameState(
            game_id="g1",
            map_name="standard",
            current_turn=0,
            current_year=1901,
            current_season="Spring",
            current_phase="Movement",
            phase_code="S1901M",
            status=GameStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            map_data=map_data,
            powers={
                "FRANCE": PowerState(
                    power_name="FRANCE",
                    home_supply_centers=[],
                    controlled_supply_centers=[],
                    is_eliminated=False,
                    orders_submitted=False,
                    last_order_time=None,
                    retreat_options={},
                    build_options=[],
                    destroy_options=[],
                )
            },
            orders={},
            pending_retreats={},
            pending_builds={},
            pending_destroys={},
            order_history=[],
        )
        mock_server.games = {}
        mock_db.get_game_state.return_value = state
        resp = client.get("/games/g1/observer_state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["game_id"] == "g1"
        assert data["orders"] == {}
        assert data["order_history"] == []
        assert "adjudication_results" in data
