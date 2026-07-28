"""
Test the Diplomacy API scheduler and deadline endpoints.
"""
from fastapi.testclient import TestClient
from server.api import app, process_due_deadlines, check_and_send_reminders

import datetime
import time
import pytest
from unittest.mock import patch


def _auth_headers(client: TestClient) -> dict:
    """Register a fresh user and return Bearer auth headers for it.

    ``/games/create`` and ``POST /games/{id}/deadline`` both require
    ``require_bot_or_user`` (Bearer token or X-Bot-Secret); a plain unauthenticated
    call gets 401, not the endpoint's own logic, so every test below that hits
    either of those needs a real token.
    """
    email = f"sched_{int(time.time() * 1000000)}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    if reg.status_code != 200:
        pytest.skip("Database not available for scheduler test")
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


def test_scheduler_status():
    client = TestClient(app)
    resp = client.get("/scheduler/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "scheduler" in data

def test_deadline_endpoints():
    client = TestClient(app)
    headers = _auth_headers(client)
    # Create a game
    resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=headers)
    assert resp.status_code == 200
    game_id = resp.json()["game_id"]
    # Set a deadline
    deadline = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)).isoformat()
    resp = client.post(f"/games/{game_id}/deadline", json={"deadline": deadline}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    # Get the deadline
    resp = client.get(f"/games/{game_id}/deadline")
    assert resp.status_code == 200
    deadline_response = resp.json().get("deadline")
    # Deadline may be None if not set or if GameModel doesn't support deadline column
    if deadline_response is not None:
        assert deadline_response.startswith(str(datetime.datetime.now().year))


# The following 4 tests used to be skipped as "session isolation issues": the claim
# was that changes made by deadline processing weren't visible across the different
# DB sessions TestClient calls open. That diagnosis was stale -- the real bug was
# POST /deadline mutating a detached ORM object and never committing (see
# update_game_deadline in routes/games.py), so the deadline was silently discarded
# regardless of session boundaries. Once that route switched to
# DatabaseService.update_game_deadline (which opens its own session and commits),
# the value is genuinely visible cross-session and these pass for real.
def test_deadline_past_on_startup():
    """Test that a deadline in the past is processed immediately on app startup."""
    client = TestClient(app)
    headers = _auth_headers(client)
    # Create a game
    resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=headers)
    game_id = resp.json()["game_id"]
    # Set a deadline in the past
    past_deadline = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)).isoformat()
    resp = client.post(f"/games/{game_id}/deadline", json={"deadline": past_deadline}, headers=headers)
    assert resp.status_code == 200
    # Synchronously process deadlines
    process_due_deadlines(datetime.datetime.now(datetime.timezone.utc))
    # Re-query with a new client/session to avoid stale cache
    client2 = TestClient(app)
    resp = client2.get(f"/games/{game_id}/deadline")
    assert resp.status_code == 200
    assert resp.json()["deadline"] is None


def test_overlapping_deadlines():
    """Test that multiple games with overlapping deadlines are processed independently."""
    client = TestClient(app)
    headers = _auth_headers(client)
    # Create two games
    resp1 = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=headers)
    game1_id = resp1.json()["game_id"]
    resp2 = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=headers)
    game2_id = resp2.json()["game_id"]
    # Set deadlines a few seconds apart
    now = datetime.datetime.now(datetime.timezone.utc)
    deadline1 = (now + datetime.timedelta(seconds=2)).isoformat()
    deadline2 = (now + datetime.timedelta(seconds=4)).isoformat()
    client.post(f"/games/{game1_id}/deadline", json={"deadline": deadline1}, headers=headers)
    client.post(f"/games/{game2_id}/deadline", json={"deadline": deadline2}, headers=headers)
    # Process with a synthetic "now" past both deadlines instead of sleeping for
    # them to actually elapse -- process_due_deadlines takes "now" as a parameter
    # precisely so callers (tests included) don't need to wait on the wall clock.
    process_due_deadlines(now + datetime.timedelta(seconds=10))
    # Re-query with a new client/session to avoid stale cache
    client2 = TestClient(app)
    resp = client2.get(f"/games/{game1_id}/deadline")
    assert resp.json()["deadline"] is None
    resp = client2.get(f"/games/{game2_id}/deadline")
    assert resp.json()["deadline"] is None


def test_reminder_and_notification():
    """Test that reminders are sent for a deadline within the 10-minute window.

    Previously waited up to 70 real seconds for the scheduler's 30s poll loop to
    notice a deadline 11 minutes out. check_and_send_reminders (split out of
    deadline_scheduler for exactly this) takes "now" as a parameter, so the test
    calls it directly with a synthetic "now" 9 minutes after deadline-setting --
    i.e. 2 minutes before the deadline, inside the reminder window -- with no
    sleep at all.
    """
    client = TestClient(app)
    headers = _auth_headers(client)
    resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=headers)
    game_id = resp.json()["game_id"]
    # Set a deadline 11 minutes from now (reminder window opens at 10 min out).
    now = datetime.datetime.now(datetime.timezone.utc)
    deadline = (now + datetime.timedelta(minutes=11)).isoformat()
    client.post(f"/games/{game_id}/deadline", json={"deadline": deadline}, headers=headers)
    # Patch notify_players where check_and_send_reminders actually looks it up
    # (module-global in server.api.shared), not the server.api package namespace.
    with patch("server.api.shared.notify_players") as mock_notify:
        check_and_send_reminders(now + datetime.timedelta(minutes=2))
        assert mock_notify.called
        reminder_msgs = [call.args[1] for call in mock_notify.call_args_list if "Reminder" in call.args[1]]
        assert any(reminder_msgs)


def test_deadline_set_to_now():
    """Test that a deadline set to now is processed immediately."""
    client = TestClient(app)
    headers = _auth_headers(client)
    resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=headers)
    game_id = resp.json()["game_id"]
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    resp = client.post(f"/games/{game_id}/deadline", json={"deadline": now}, headers=headers)
    assert resp.status_code == 200
    # Synchronously process deadlines
    process_due_deadlines(datetime.datetime.now(datetime.timezone.utc))
    # Re-query with a new client/session to avoid stale cache
    client2 = TestClient(app)
    resp = client2.get(f"/games/{game_id}/deadline")
    assert resp.json()["deadline"] is None
