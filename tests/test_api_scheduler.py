"""
Test the Diplomacy API scheduler and deadline endpoints.
"""
from fastapi.testclient import TestClient
from server.api import app, process_due_deadlines, check_and_send_reminders

import datetime
import time
import pytest
from unittest.mock import patch

from tests.table_helpers import fill_with_dummies
from server.api.shared import db_service


def _auth_headers(client: TestClient) -> dict:
    """Register a fresh user and return Bearer auth headers for it.

    ``/games/create`` requires ``require_bot_or_user`` (Bearer token or
    X-Bot-Secret); a plain unauthenticated call gets 401, not the endpoint's own
    logic, so every test below that hits it needs a real token.
    """
    email = f"sched_{int(time.time() * 1000000)}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    if reg.status_code != 200:
        pytest.skip("Database not available for scheduler test")
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


def _create_game_as_player(client: TestClient, headers: dict) -> str:
    """Create a game and seat its creator as FRANCE.

    ``POST /games/{id}/deadline`` is for the game's *players* (Track T): a
    Bearer user who merely created the game is not one until they join. The
    other six powers are dummies: only a full table is processed (BA6).
    """
    resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=headers)
    assert resp.status_code == 200, resp.text
    game_id = resp.json()["game_id"]
    join = client.post(f"/games/{game_id}/join", json={"power": "FRANCE"}, headers=headers)
    assert join.status_code == 200, join.text
    fill_with_dummies(game_id)
    return game_id


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
    game_id = _create_game_as_player(client, headers)
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
    game_id = _create_game_as_player(client, headers)
    # Set a deadline in the past
    past_deadline = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
    # The route refuses a past deadline (BL5), so arm it directly.
    db_service.update_game_deadline(int(game_id), past_deadline)
    # Synchronously process deadlines
    process_due_deadlines(datetime.datetime.now(datetime.timezone.utc))
    # Re-query with a new client/session to avoid stale cache
    client2 = TestClient(app)
    resp = client2.get(f"/games/{game_id}/deadline")
    assert resp.status_code == 200
    assert resp.json()["deadline"] is None
    # The scheduler path used to take no snapshot at all, unlike the manual
    # process_turn route -- so `/history/{turn}` and the bot's `/replay` had a
    # permanent hole for every turn a missed deadline advanced.
    snapshots = client2.get(f"/games/{game_id}/snapshots").json()["snapshots"]
    assert sorted(s["turn"] for s in snapshots) == [0, 1], "the deadline scheduler recorded no snapshot for the processed turn"


def test_overlapping_deadlines():
    """Test that multiple games with overlapping deadlines are processed independently."""
    client = TestClient(app)
    headers = _auth_headers(client)
    # Create two games
    game1_id = _create_game_as_player(client, headers)
    game2_id = _create_game_as_player(client, headers)
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
    for gid in (game1_id, game2_id):
        assert sorted(s["turn"] for s in client2.get(f"/games/{gid}/snapshots").json()["snapshots"]) == [0, 1], (
            f"game {gid} was processed by the scheduler but got no snapshot"
        )


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
    game_id = _create_game_as_player(client, headers)
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


def _reminders_sent(game_id: str, now: datetime.datetime) -> int:
    """Run one reminder pass at ``now``; how many reminders it sent ``game_id``."""
    with patch("server.api.shared.notify_players") as mock_notify:
        check_and_send_reminders(now)
    return sum(
        1 for call in mock_notify.call_args_list
        if call.args[0] == int(game_id) and "Reminder" in call.args[1]
    )


def _restart_api_process() -> None:
    """What a restart or a second uvicorn worker loses: the process's memory.
    Before BN2 the reminder was remembered in ``shared.reminder_sent``; now
    nothing in the process remembers it, so this only clears that if present."""
    import server.api.shared as shared

    vars(shared).get("reminder_sent", {}).clear()


def test_reminder_is_not_resent_after_a_restart_inside_the_window():
    """BN2: an API restart (a deploy) or a second worker inside the 10-minute
    window used to send every player the reminder again."""
    client = TestClient(app)
    headers = _auth_headers(client)
    game_id = _create_game_as_player(client, headers)
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    deadline = now + datetime.timedelta(minutes=8)
    db_service.update_game_deadline(int(game_id), deadline)

    assert _reminders_sent(game_id, now) == 1
    _restart_api_process()
    assert _reminders_sent(game_id, now + datetime.timedelta(minutes=1)) == 0
    assert db_service.get_game_by_id(int(game_id)).reminded_deadline == deadline.replace(tzinfo=None)


def test_a_changed_deadline_is_reminded_again():
    """A new deadline -- a different value, or the same value written again for
    a new phase -- gets its own reminder; claiming one is single-winner."""
    client = TestClient(app)
    headers = _auth_headers(client)
    game_id = _create_game_as_player(client, headers)
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    first = now + datetime.timedelta(minutes=8)
    db_service.update_game_deadline(int(game_id), first)
    assert _reminders_sent(game_id, now) == 1

    second = now + datetime.timedelta(minutes=9)
    db_service.update_game_deadline(int(game_id), second)
    assert _reminders_sent(game_id, now) == 1
    assert _reminders_sent(game_id, now) == 0

    db_service.update_game_deadline(int(game_id), second)
    assert db_service.claim_deadline_reminder(int(game_id), second) is True
    assert db_service.claim_deadline_reminder(int(game_id), second) is False
    # A stale read of an old deadline claims nothing.
    assert db_service.claim_deadline_reminder(int(game_id), first) is False


def test_deadline_set_to_now():
    """Test that a deadline set to now is processed immediately."""
    client = TestClient(app)
    headers = _auth_headers(client)
    game_id = _create_game_as_player(client, headers)
    db_service.update_game_deadline(int(game_id), datetime.datetime.now(datetime.timezone.utc))
    # Synchronously process deadlines
    process_due_deadlines(datetime.datetime.now(datetime.timezone.utc))
    # Re-query with a new client/session to avoid stale cache
    client2 = TestClient(app)
    resp = client2.get(f"/games/{game_id}/deadline")
    assert resp.json()["deadline"] is None
    assert sorted(s["turn"] for s in client2.get(f"/games/{game_id}/snapshots").json()["snapshots"]) == [0, 1]


def test_manual_processing_never_imposes_a_deadline():
    """Track N (a): a game with no deadline stays that way after a manual
    process_turn. Until v2.7.72 the route re-armed a hard-coded +24h, after which
    the scheduler would process the next phase with missing powers' units
    holding -- then clear it, so alternate phases had an auto-deadline."""
    client = TestClient(app)
    headers = _auth_headers(client)
    game_id = _create_game_as_player(client, headers)
    assert client.get(f"/games/{game_id}/deadline").json()["deadline"] is None

    resp = client.post(f"/games/{game_id}/process_turn", headers={"X-Bot-Secret": "test_bot_secret_for_tests"})
    assert resp.status_code == 200, resp.text
    assert client.get(f"/games/{game_id}/deadline").json()["deadline"] is None


def test_manual_processing_spends_an_explicit_deadline():
    """An explicitly set deadline is scoped to the phase it was set for: once the
    phase is processed by hand it is cleared rather than carried over."""
    client = TestClient(app)
    headers = _auth_headers(client)
    game_id = _create_game_as_player(client, headers)
    future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=6)).isoformat()
    assert client.post(f"/games/{game_id}/deadline", json={"deadline": future}, headers=headers).status_code == 200
    assert client.get(f"/games/{game_id}/deadline").json()["deadline"] is not None

    resp = client.post(f"/games/{game_id}/process_turn", headers={"X-Bot-Secret": "test_bot_secret_for_tests"})
    assert resp.status_code == 200, resp.text
    assert client.get(f"/games/{game_id}/deadline").json()["deadline"] is None


def test_phase_length_seconds_stored_at_creation_does_not_arm_a_deadline():
    """phase_length_seconds is stored, but creation still imposes no deadline
    (Track N: a deadline exists only when set explicitly)."""
    client = TestClient(app)
    headers = _auth_headers(client)
    resp = client.post(
        "/games/create",
        json={"map_name": "standard", "initial_phase": "Movement", "phase_length_seconds": 600},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    game_id = resp.json()["game_id"]
    deadline = client.get(f"/games/{game_id}/deadline").json()
    assert deadline["deadline"] is None
    assert deadline["phase_length_seconds"] == 600


def test_deadline_route_can_arm_from_phase_length_explicitly():
    """POST /deadline with phase_length_seconds and no explicit deadline arms
    one from that length -- this is the *only* place phase_length_seconds
    affects the deadline; nothing does so automatically after a turn."""
    client = TestClient(app)
    headers = _auth_headers(client)
    game_id = _create_game_as_player(client, headers)

    resp = client.post(
        f"/games/{game_id}/deadline", json={"phase_length_seconds": 300}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["phase_length_seconds"] == 300
    deadline_str = resp.json()["deadline"]
    assert deadline_str is not None
    parsed = datetime.datetime.fromisoformat(deadline_str)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    remaining = parsed - datetime.datetime.now(datetime.timezone.utc)
    assert datetime.timedelta(minutes=4) < remaining < datetime.timedelta(minutes=6)

    resp = client.post(
        f"/games/{game_id}/deadline", json={"phase_length_seconds": -1}, headers=headers
    )
    assert resp.status_code == 400


@pytest.mark.parametrize("offset", [datetime.timedelta(0), datetime.timedelta(minutes=-1)])
@pytest.mark.parametrize("aware", [True, False])
def test_deadline_in_the_past_is_refused(offset, aware):
    """BL5: a deadline at or before now is a 422, and nothing is stored."""
    client = TestClient(app)
    headers = _auth_headers(client)
    game_id = _create_game_as_player(client, headers)
    when = datetime.datetime.now(datetime.timezone.utc) + offset - datetime.timedelta(seconds=1)
    if not aware:
        when = when.replace(tzinfo=None)
    resp = client.post(f"/games/{game_id}/deadline", json={"deadline": when.isoformat()}, headers=headers)
    assert resp.status_code == 422
    assert resp.json()["detail"] == "That deadline has already passed. Choose a time in the future."
    assert client.get(f"/games/{game_id}/deadline").json()["deadline"] is None
