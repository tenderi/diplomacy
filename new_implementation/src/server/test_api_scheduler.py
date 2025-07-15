"""
Test the Diplomacy API scheduler and deadline endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from server.api import app

def test_scheduler_status():
    client = TestClient(app)
    resp = client.get("/scheduler/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "scheduler" in data

def test_deadline_endpoints():
    client = TestClient(app)
    # Create a game
    resp = client.post("/games/create", json={"map_name": "standard"})
    assert resp.status_code == 200
    game_id = resp.json()["game_id"]
    # Set a deadline
    import datetime
    deadline = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)).isoformat()
    resp = client.post(f"/games/{game_id}/deadline", json={"deadline": deadline})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    # Get the deadline
    resp = client.get(f"/games/{game_id}/deadline")
    assert resp.status_code == 200
    assert resp.json()["deadline"].startswith(str(datetime.datetime.now().year))
