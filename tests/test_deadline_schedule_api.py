"""Weekly deadline schedules through the API: ``POST /games/{id}/deadline/schedule``,
``GET /games/{id}/deadline``, arming when the game fills, and re-arming after
every processed turn."""
from __future__ import annotations

import itertools
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from server.deadline_schedule import parse_schedule

pytestmark = [pytest.mark.integration, pytest.mark.database]

POWERS = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]
_seq = itertools.count(1)


def _register(client: TestClient, tag: str) -> dict:
    stamp = f"{int(time.time() * 1000000)}_{tag}_{next(_seq)}"
    resp = client.post(
        "/auth/register", json={"email": f"dls_{stamp}@example.com", "password": "testpass123"}
    )
    if resp.status_code != 200:
        pytest.skip("Database not available for deadline-schedule test")
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _game(client: TestClient, seated: list[str], **create: object) -> tuple[str, dict[str, dict]]:
    """A game FRANCE's user created, with ``seated`` powers joined."""
    users = {p: _register(client, p) for p in POWERS}
    resp = client.post("/games/create", json={"map_name": "standard", **create}, headers=users["FRANCE"])
    assert resp.status_code == 200, resp.text
    game_id = str(resp.json()["game_id"])
    for power in seated:
        r = client.post(f"/games/{game_id}/join", json={"power": power}, headers=users[power])
        assert r.status_code == 200, f"join {power}: {r.text}"
    return game_id, users


def _deadline(client: TestClient, game_id: str) -> datetime | None:
    raw = client.get(f"/games/{game_id}/deadline").json()["deadline"]
    return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc) if raw else None


def _expected(text: str, tz: str = "UTC") -> set[datetime]:
    """The slot a phase armed around now gets (two readings, in case a slot
    boundary falls between computing it here and in the API)."""
    sched = parse_schedule(text, tz)
    now = datetime.now(timezone.utc)
    return {sched.next_deadline(now), sched.next_deadline(now + timedelta(seconds=5))}


def test_setting_a_schedule_on_a_started_game_arms_the_next_slot_and_tells_the_others():
    client = TestClient(app)
    game_id, users = _game(client, POWERS)
    with patch("server.api.routes.games.notify_players") as notify:
        resp = client.post(
            f"/games/{game_id}/deadline/schedule",
            json={"schedule": "Mon,Wed,Fri 16:00", "timezone": "Europe/Helsinki"},
            headers=users["ITALY"],
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["schedule"] == {
        "timezone": "Europe/Helsinki",
        "slots": [
            {"day": "MON", "time": "16:00"},
            {"day": "WED", "time": "16:00"},
            {"day": "FRI", "time": "16:00"},
        ],
        "description": "Mon, Wed, Fri at 16:00 (Europe/Helsinki)",
    }
    armed = datetime.fromisoformat(body["deadline"])
    assert armed in _expected("Mon,Wed,Fri 16:00", "Europe/Helsinki")
    assert _deadline(client, game_id) == armed
    assert client.get(f"/games/{game_id}/deadline").json()["schedule"] == body["schedule"]
    text = notify.call_args[0][1]
    assert text.startswith(
        f"Game {game_id}'s deadlines are now Mon, Wed, Fri at 16:00 (Europe/Helsinki). "
        f"This phase's deadline: "
    )
    assert "Europe/Helsinki)." in text


def test_a_schedule_set_before_the_game_fills_arms_when_the_last_seat_is_taken():
    client = TestClient(app)
    game_id, users = _game(client, POWERS[:-1])
    resp = client.post(
        f"/games/{game_id}/deadline/schedule", json={"schedule": "daily 12:00"}, headers=users["FRANCE"]
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["deadline"] is None
    assert _deadline(client, game_id) is None

    with patch("server.api.routes.games.notify_players") as notify:
        r = client.post(f"/games/{game_id}/join", json={"power": "TURKEY"}, headers=users["TURKEY"])
    assert r.status_code == 200, r.text
    assert _deadline(client, game_id) in _expected("daily 12:00")
    started = [c[0][1] for c in notify.call_args_list if "is now full" in c[0][1]]
    assert len(started) == 1
    assert "The game has started! Good luck to all players. First deadline: " in started[0]


def test_a_schedule_given_at_creation_arms_when_the_game_fills():
    client = TestClient(app)
    game_id, users = _game(client, POWERS[:-1], deadline_schedule="sat 10:00", deadline_timezone="UTC")
    assert client.get(f"/games/{game_id}/deadline").json()["schedule"]["description"] == "Sat at 10:00 (UTC)"
    assert _deadline(client, game_id) is None
    client.post(f"/games/{game_id}/join", json={"power": "TURKEY"}, headers=users["TURKEY"])
    assert _deadline(client, game_id) in _expected("sat 10:00")


def test_create_refuses_an_unreadable_schedule():
    client = TestClient(app)
    headers = _register(client, "creator")
    resp = client.post(
        "/games/create", json={"map_name": "standard", "deadline_schedule": "someday 16:00"}, headers=headers
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "'someday' is not a day of the week; use Mon, Tue, ... Sun."


def test_every_processed_turn_arms_the_next_slot_and_says_when():
    client = TestClient(app)
    game_id, users = _game(client, POWERS)
    client.post(f"/games/{game_id}/deadline/schedule", json={"schedule": "daily 12:00"}, headers=users["FRANCE"])
    # Pull this phase's deadline into the past, as if the slot had arrived.
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    assert client.post(f"/games/{game_id}/deadline", json={"deadline": past}, headers=users["FRANCE"]).status_code == 200

    with patch("server.api.shared.notify_players") as notify:
        api_shared.process_due_deadlines(datetime.now(timezone.utc))

    assert client.get(f"/games/{game_id}/state").json()["phase"] == "F1901M"
    armed = _deadline(client, game_id)
    assert armed in _expected("daily 12:00")
    processed = [
        c[0][1] for c in notify.call_args_list
        if c[0][0] == int(game_id) and "has been processed" in c[0][1]
    ]
    assert processed == [
        f"The turn has been processed for game {game_id} because its deadline passed. "
        f"Your next orders are due. Next deadline: {api_shared.format_deadline_utc(armed)}."
    ]


def test_without_a_schedule_a_processed_turn_still_leaves_no_deadline():
    client = TestClient(app)
    game_id, users = _game(client, POWERS)
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    client.post(f"/games/{game_id}/deadline", json={"deadline": past}, headers=users["FRANCE"])
    api_shared.process_due_deadlines(datetime.now(timezone.utc))
    assert client.get(f"/games/{game_id}/state").json()["phase"] == "F1901M"
    assert _deadline(client, game_id) is None


def test_removing_the_schedule_keeps_the_current_deadline():
    client = TestClient(app)
    game_id, users = _game(client, POWERS)
    armed = client.post(
        f"/games/{game_id}/deadline/schedule", json={"schedule": "daily 12:00"}, headers=users["FRANCE"]
    ).json()["deadline"]
    resp = client.post(f"/games/{game_id}/deadline/schedule", json={"schedule": None}, headers=users["ENGLAND"])
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "ok", "schedule": None, "deadline": None}
    assert client.get(f"/games/{game_id}/deadline").json()["schedule"] is None
    assert _deadline(client, game_id) == datetime.fromisoformat(armed).replace(tzinfo=timezone.utc)


def test_only_players_may_set_a_schedule():
    client = TestClient(app)
    game_id, _users = _game(client, ["FRANCE"])
    outsider = _register(client, "outsider")
    resp = client.post(f"/games/{game_id}/deadline/schedule", json={"schedule": "mon 16:00"}, headers=outsider)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "You are not a player in this game."


def test_an_unreadable_schedule_is_refused_and_nothing_changes():
    client = TestClient(app)
    game_id, users = _game(client, ["FRANCE"])
    resp = client.post(
        f"/games/{game_id}/deadline/schedule",
        json={"schedule": "mon 16:00", "timezone": "Mars/Olympus"},
        headers=users["FRANCE"],
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == (
        "Unknown timezone 'Mars/Olympus'; use an IANA name such as UTC or Europe/Helsinki."
    )
    assert client.get(f"/games/{game_id}/deadline").json()["schedule"] is None


def test_an_unknown_game_is_404():
    client = TestClient(app)
    headers = _register(client, "nogame")
    resp = client.post("/games/99999999/deadline/schedule", json={"schedule": "mon 16:00"}, headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Game not found"
