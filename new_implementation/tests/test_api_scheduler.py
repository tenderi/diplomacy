"""
Test the Diplomacy API scheduler and deadline endpoints.
"""
from fastapi.testclient import TestClient
from server.api import app, process_due_deadlines, check_and_send_reminders

import datetime
import time
import pytest
from unittest.mock import patch


def _as_utc(iso: str) -> datetime.datetime:
    """Parse an API deadline string as an aware UTC datetime.

    `games.deadline` is a naive UTC column (see `utcnow_naive`), so the API
    renders it without an offset; comparing it to `now(timezone.utc)` needs the
    tzinfo put back rather than assumed.
    """
    parsed = datetime.datetime.fromisoformat(iso)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


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
    before = client.get(f"/games/{game_id}/state").json()["phase"]
    # Synchronously process deadlines
    process_due_deadlines(datetime.datetime.now(datetime.timezone.utc))
    # Re-query with a new client/session to avoid stale cache
    client2 = TestClient(app)
    resp = client2.get(f"/games/{game_id}/deadline")
    assert resp.status_code == 200
    assert client2.get(f"/games/{game_id}/state").json()["phase"] != before

    # The deadline is **re-armed for the new phase**, not cleared. This asserted
    # `is None` until K1, which is the bug it was pinning: the scheduler set the
    # deadline to NULL after processing, so the first missed deadline in a game
    # was also its last -- every later turn waited for a human. The manual route
    # re-armed +24h; only this path did not.
    new_deadline = resp.json()["deadline"]
    assert new_deadline is not None, "the scheduler left the game with no deadline (the K1 bug)"
    assert _as_utc(new_deadline) > datetime.datetime.now(datetime.timezone.utc)


def test_deadline_is_not_rearmed_when_the_game_has_no_phase_length():
    """`phase_length_seconds=0` means "no automatic deadline" (the old NO_DEADLINE).

    The turn still processes when a deadline is set by hand and passes; what must
    not happen is a new deadline appearing on its own afterwards.
    """
    client = TestClient(app)
    headers = _auth_headers(client)
    resp = client.post(
        "/games/create",
        json={"map_name": "standard", "initial_phase": "Movement", "phase_length_seconds": 0},
        headers=headers,
    )
    game_id = resp.json()["game_id"]
    assert client.get(f"/games/{game_id}/deadline").json()["deadline"] is None

    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)).isoformat()
    client.post(f"/games/{game_id}/deadline", json={"deadline": past}, headers=headers)
    before = client.get(f"/games/{game_id}/state").json()["phase"]
    process_due_deadlines(datetime.datetime.now(datetime.timezone.utc))

    client2 = TestClient(app)
    assert client2.get(f"/games/{game_id}/state").json()["phase"] != before, "the turn did not process"
    assert client2.get(f"/games/{game_id}/deadline").json()["deadline"] is None


def test_phase_length_drives_the_next_deadline():
    """A game's phase length is re-applied after every processed turn (K2).

    Before this, 24 h was hardcoded in the manual process-turn route and nothing
    re-armed at all on the scheduler path, so a fast game (10-minute phases) was
    impossible without a human re-setting /deadline after every single turn.
    """
    client = TestClient(app)
    headers = _auth_headers(client)
    resp = client.post(
        "/games/create",
        json={"map_name": "standard", "initial_phase": "Movement", "phase_length_seconds": 600},
        headers=headers,
    )
    game_id = resp.json()["game_id"]

    # Armed at creation, ~10 minutes out.
    first = client.get(f"/games/{game_id}/deadline").json()
    assert first["phase_length_seconds"] == 600
    now = datetime.datetime.now(datetime.timezone.utc)
    assert datetime.timedelta(minutes=9) < _as_utc(first["deadline"]) - now < datetime.timedelta(minutes=11)

    past = (now - datetime.timedelta(minutes=1)).isoformat()
    client.post(f"/games/{game_id}/deadline", json={"deadline": past}, headers=headers)
    process_due_deadlines(datetime.datetime.now(datetime.timezone.utc))

    client2 = TestClient(app)
    after = _as_utc(client2.get(f"/games/{game_id}/deadline").json()["deadline"])
    # The *new* phase gets another 10 minutes, not 24 hours.
    assert datetime.timedelta(minutes=9) < after - datetime.datetime.now(datetime.timezone.utc) < datetime.timedelta(minutes=11)


def test_phase_length_can_be_changed_on_a_running_game():
    """POST /deadline with phase_length_seconds re-arms the current phase too."""
    client = TestClient(app)
    headers = _auth_headers(client)
    game_id = client.post(
        "/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=headers
    ).json()["game_id"]

    resp = client.post(
        f"/games/{game_id}/deadline", json={"phase_length_seconds": 300}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["phase_length_seconds"] == 300
    remaining = _as_utc(resp.json()["deadline"]) - datetime.datetime.now(datetime.timezone.utc)
    assert datetime.timedelta(minutes=4) < remaining < datetime.timedelta(minutes=6)

    assert client.post(
        f"/games/{game_id}/deadline", json={"phase_length_seconds": -1}, headers=headers
    ).status_code == 400


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
    # Both games processed and both got a fresh deadline for their new phase
    # (they were asserted to be `None` here until K1 -- see
    # test_deadline_past_on_startup for why that was the bug, not the contract).
    for gid in (game1_id, game2_id):
        deadline = client2.get(f"/games/{gid}/deadline").json()["deadline"]
        assert deadline is not None, f"game {gid} was left with no deadline"
        assert _as_utc(deadline) > datetime.datetime.now(datetime.timezone.utc)


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
    before = client.get(f"/games/{game_id}/state").json()["phase"]
    # Synchronously process deadlines
    process_due_deadlines(datetime.datetime.now(datetime.timezone.utc))
    # Re-query with a new client/session to avoid stale cache
    client2 = TestClient(app)
    assert client2.get(f"/games/{game_id}/state").json()["phase"] != before
    # Re-armed for the next phase rather than cleared (K1).
    assert client2.get(f"/games/{game_id}/deadline").json()["deadline"] is not None
