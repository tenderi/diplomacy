"""
Tests for tournament API endpoints.

Uses mocked db_service to avoid database dependency.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from server.api import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_tournament():
    return {
        "id": 1,
        "name": "Spring Cup 1901",
        "status": "pending",
        "bracket_type": "single_elimination",
        "start_date": None,
        "end_date": None,
        "created_at": "2025-03-02T12:00:00",
    }


@pytest.mark.unit
class TestTournamentsAPI:
    """Test tournament CRUD and bracket endpoints."""

    @patch("server.api.routes.tournaments.db_service")
    def test_create_tournament_success(self, mock_db, client, sample_tournament):
        mock_db.create_tournament.return_value = sample_tournament
        resp = client.post(
            "/tournaments",
            json={"name": "Spring Cup 1901", "bracket_type": "single_elimination"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["tournament"]["name"] == "Spring Cup 1901"
        assert data["tournament"]["id"] == 1

    @patch("server.api.routes.tournaments.db_service")
    def test_create_tournament_validation_error(self, mock_db, client):
        mock_db.create_tournament.side_effect = ValueError("Tournament name must be non-empty")
        resp = client.post("/tournaments", json={"name": ""})
        assert resp.status_code == 400

    @patch("server.api.routes.tournaments.db_service")
    def test_list_tournaments(self, mock_db, client, sample_tournament):
        mock_db.list_tournaments.return_value = [sample_tournament]
        resp = client.get("/tournaments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["count"] == 1
        assert len(data["tournaments"]) == 1

    @patch("server.api.routes.tournaments.db_service")
    def test_get_tournament_success(self, mock_db, client, sample_tournament):
        mock_db.get_tournament.return_value = sample_tournament
        resp = client.get("/tournaments/1")
        assert resp.status_code == 200
        assert resp.json()["tournament"]["name"] == "Spring Cup 1901"

    @patch("server.api.routes.tournaments.db_service")
    def test_get_tournament_not_found(self, mock_db, client):
        mock_db.get_tournament.return_value = None
        resp = client.get("/tournaments/999")
        assert resp.status_code == 404

    @patch("server.api.routes.tournaments.db_service")
    def test_get_bracket_success(self, mock_db, client, sample_tournament):
        mock_db.get_tournament_bracket.return_value = {
            "tournament": sample_tournament,
            "games_by_round": {1: [{"game_id": "1", "round_number": 1}]},
            "players": [],
        }
        resp = client.get("/tournaments/1/bracket")
        assert resp.status_code == 200
        data = resp.json()
        assert "games_by_round" in data
        assert "players" in data

    @patch("server.api.routes.tournaments.db_service")
    def test_add_game_to_tournament(self, mock_db, client):
        mock_db.add_game_to_tournament.return_value = None
        resp = client.post(
            "/tournaments/1/games",
            json={"game_id": "42", "round_number": 1, "bracket_position": "1"},
        )
        assert resp.status_code == 200
        mock_db.add_game_to_tournament.assert_called_once()
        call_kw = mock_db.add_game_to_tournament.call_args[1]
        assert call_kw["tournament_id"] == 1
        assert call_kw["game_id"] == "42"

    @patch("server.api.routes.tournaments.db_service")
    def test_update_tournament_status(self, mock_db, client):
        resp = client.put("/tournaments/1/status", json={"status": "active"})
        assert resp.status_code == 200
        mock_db.update_tournament_status.assert_called_once_with(1, "active")
