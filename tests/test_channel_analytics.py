"""
Tests for channel analytics API endpoints.

Tests GET /games/{game_id}/channel/analytics, .../analytics/summary,
.../analytics/engagement, and .../analytics/players.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from server.api import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_channel_info():
    """Channel info returned when game is linked."""
    return {
        "channel_id": "-1001234567890",
        "channel_name": "Test Channel",
        "settings": {"auto_post_maps": True},
    }


@pytest.fixture
def sample_analytics_events():
    """Sample analytics events for list endpoint."""
    return [
        {
            "id": 1,
            "game_id": "1",
            "channel_id": "-1001234567890",
            "event_type": "message_posted",
            "event_subtype": "map",
            "user_id": None,
            "power": None,
            "event_data": {"message_id": 101},
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        },
        {
            "id": 2,
            "game_id": "1",
            "channel_id": "-1001234567890",
            "event_type": "player_activity",
            "event_subtype": None,
            "user_id": 42,
            "power": "FRANCE",
            "event_data": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]


@pytest.fixture
def sample_analytics_summary():
    """Sample summary for summary/engagement endpoints."""
    return {
        "total_events": 10,
        "events_by_type": {"message_posted": 6, "player_activity": 4},
        "events_by_subtype": {"map": 2, "broadcast": 2, "notification": 2},
        "unique_users": 3,
        "message_count": 6,
        "player_activity_count": 4,
    }


@pytest.mark.unit
@pytest.mark.channels
class TestChannelAnalyticsEndpoints:
    """Test channel analytics API routes."""

    @patch("server.api.routes.channels.db_service")
    def test_get_analytics_returns_404_when_game_not_linked(
        self, mock_db, client, mock_channel_info
    ):
        mock_db.get_game_channel_info.return_value = None
        resp = client.get("/games/game_99/channel/analytics")
        assert resp.status_code == 404
        mock_db.get_channel_analytics.assert_not_called()

    @patch("server.api.routes.channels.db_service")
    def test_get_analytics_returns_events_when_linked(
        self, mock_db, client, mock_channel_info, sample_analytics_events
    ):
        mock_db.get_game_channel_info.return_value = mock_channel_info
        mock_db.get_channel_analytics.return_value = sample_analytics_events
        resp = client.get("/games/game_1/channel/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["game_id"] == "game_1"
        assert data["channel_id"] == "-1001234567890"
        assert data["event_count"] == 2
        assert len(data["events"]) == 2
        assert data["events"][0]["event_type"] == "message_posted"
        assert data["events"][1]["event_type"] == "player_activity"

    @patch("server.api.routes.channels.db_service")
    def test_get_analytics_accepts_query_params(
        self, mock_db, client, mock_channel_info, sample_analytics_events
    ):
        mock_db.get_game_channel_info.return_value = mock_channel_info
        mock_db.get_channel_analytics.return_value = sample_analytics_events
        resp = client.get(
            "/games/game_1/channel/analytics",
            params={"event_type": "message_posted", "channel_id": "-1001234567890"},
        )
        assert resp.status_code == 200
        mock_db.get_channel_analytics.assert_called_once()
        call_kw = mock_db.get_channel_analytics.call_args[1]
        assert call_kw["event_type"] == "message_posted"
        assert call_kw["channel_id"] == "-1001234567890"

    @patch("server.api.routes.channels.db_service")
    def test_get_analytics_summary_returns_404_when_not_linked(self, mock_db, client):
        mock_db.get_game_channel_info.return_value = None
        resp = client.get("/games/game_99/channel/analytics/summary")
        assert resp.status_code == 404
        mock_db.get_channel_analytics_summary.assert_not_called()

    @patch("server.api.routes.channels.db_service")
    def test_get_analytics_summary_returns_aggregates(
        self, mock_db, client, mock_channel_info, sample_analytics_summary
    ):
        mock_db.get_game_channel_info.return_value = mock_channel_info
        mock_db.get_channel_analytics_summary.return_value = sample_analytics_summary
        resp = client.get("/games/game_1/channel/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "summary" in data
        assert data["summary"]["total_events"] == 10
        assert data["summary"]["message_count"] == 6
        assert data["summary"]["unique_users"] == 3

    @patch("server.api.routes.channels.db_service")
    def test_get_engagement_metrics_returns_metrics(
        self, mock_db, client, mock_channel_info, sample_analytics_summary
    ):
        mock_db.get_game_channel_info.return_value = mock_channel_info
        mock_db.get_channel_analytics_summary.return_value = sample_analytics_summary
        resp = client.get("/games/game_1/channel/analytics/engagement")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "metrics" in data
        m = data["metrics"]
        assert m["total_events"] == 10
        assert m["message_count"] == 6
        assert m["player_activity_count"] == 4
        assert m["unique_users"] == 3
        assert m["engagement_rate"] == 40.0  # 4/10 * 100
        assert "events_by_type" in m
        assert "events_by_subtype" in m

    @patch("server.api.routes.channels.db_service")
    def test_get_player_activity_stats_returns_404_when_not_linked(self, mock_db, client):
        mock_db.get_game_channel_info.return_value = None
        resp = client.get("/games/game_99/channel/analytics/players")
        assert resp.status_code == 404

    @patch("server.api.routes.channels.db_service")
    def test_get_player_activity_stats_returns_players(
        self, mock_db, client, mock_channel_info, sample_analytics_events
    ):
        # Use only player_activity events for this endpoint
        player_events = [e for e in sample_analytics_events if e["event_type"] == "player_activity"]
        mock_db.get_game_channel_info.return_value = mock_channel_info
        mock_db.get_channel_analytics.return_value = player_events
        resp = client.get("/games/game_1/channel/analytics/players")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "players" in data
        assert data["player_count"] >= 0
        mock_db.get_channel_analytics.assert_called_once()
        call_kw = mock_db.get_channel_analytics.call_args[1]
        assert call_kw["event_type"] == "player_activity"
