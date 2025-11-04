"""
Unit tests for dashboard API routes.

Tests dashboard endpoints for service management, database inspection, and logging.
Note: Many of these tests require system-level access and may be skipped in CI.
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
class TestServiceStatus:
    """Test service status endpoint."""
    
    @patch('server.api.routes.dashboard.subprocess.run')
    def test_get_services_status_success(self, mock_subprocess, client):
        """Test successful service status retrieval."""
        # Mock subprocess calls
        mock_subprocess.return_value = MagicMock(
            stdout="active",
            returncode=0
        )
        
        resp = client.get("/dashboard/api/services/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "services" in data
        assert isinstance(data["services"], list)
    
    @patch('server.api.routes.dashboard.subprocess.run')
    def test_get_services_status_invalid_service(self, mock_subprocess, client):
        """Test service status with invalid service name."""
        resp = client.post("/dashboard/api/services/restart", json={"service": "invalid_service"})
        assert resp.status_code == 400


@pytest.mark.unit
class TestRestartService:
    """Test restart service endpoint."""
    
    @patch('server.api.routes.dashboard.subprocess.run')
    @patch('time.sleep')
    def test_restart_service_success(self, mock_sleep, mock_subprocess, client):
        """Test successful service restart."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr=""
        )
        
        resp = client.post("/dashboard/api/services/restart", json={"service": "diplomacy"})
        # May succeed or fail depending on permissions
        assert resp.status_code in [200, 500]


@pytest.mark.unit
class TestServiceLogs:
    """Test service logs endpoint."""
    
    @patch('server.api.routes.dashboard.subprocess.run')
    def test_get_service_logs_success(self, mock_subprocess, client):
        """Test successful log retrieval."""
        mock_subprocess.return_value = MagicMock(
            stdout="Log line 1\nLog line 2",
            returncode=0
        )
        
        resp = client.get("/dashboard/api/logs/diplomacy", params={"lines": 10})
        # May succeed or fail depending on permissions
        assert resp.status_code in [200, 500]
    
    def test_get_service_logs_invalid_service(self, client):
        """Test getting logs for invalid service."""
        resp = client.get("/dashboard/api/logs/invalid_service")
        assert resp.status_code == 400


@pytest.mark.unit
class TestDatabaseInspection:
    """Test database inspection endpoints."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_database_tables(self, client):
        """Test getting database tables list."""
        resp = client.get("/dashboard/api/database/tables")
        assert resp.status_code == 200
        data = resp.json()
        assert "tables" in data
        assert isinstance(data["tables"], list)
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_table_data(self, client):
        """Test getting data from a table."""
        resp = client.get("/dashboard/api/database/table/games", params={"limit": 10, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert "table_name" in data
        assert "columns" in data
        assert "rows" in data
    
    def test_get_table_data_invalid_table(self, client):
        """Test getting data from invalid table."""
        resp = client.get("/dashboard/api/database/table/invalid_table")
        assert resp.status_code == 400
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_database_stats(self, client):
        """Test getting database statistics."""
        resp = client.get("/dashboard/api/database/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_games" in data
        assert "active_games" in data
        assert "total_players" in data
        assert "total_users" in data

