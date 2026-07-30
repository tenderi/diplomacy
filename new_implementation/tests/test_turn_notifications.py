"""Both `process_turn` triggers must notify the same people (G3).

Before this, the two paths told players wildly different amounts:

- **deadline-triggered** (`api/shared.py:process_due_deadlines`) DM'd every player,
  reset the reminder flag, and posted a notification plus a freshly rendered map
  to any linked channel;
- **manually triggered** (`POST /games/{id}/process_turn`) notified **only** when
  the game had just ended. The ordinary case — everyone submitted, one player
  pressed the button — sent nothing to the other six players and posted nothing
  to the channel.

So the failure case was richly instrumented and the success case was silent. Both
now go through `shared.notify_turn_processed`; these tests pin that they agree, by
driving both triggers against the *same* fake notifier and comparing recipients.

The interesting assertion is not "a notification was sent" but "the same set of
players is reached either way, minus the caller" — a bolt-on `notify_players` call
on the manual path would satisfy the former while still drifting on the latter.
"""
from __future__ import annotations

import datetime
import itertools
import time
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.api import app, process_due_deadlines
from server.api import shared as api_shared

REQUIRED_POWERS = [
    "ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY",
]


_telegram_seq = itertools.count(1)


def _register(client: TestClient, tag: str) -> tuple[dict, str]:
    """Register a user with a linked numeric telegram_id.

    The telegram_id is set through ``DatabaseService.set_user_telegram_id`` rather
    than the real ``POST /auth/telegram/link`` flow, which needs a one-time link
    code *and* is per-IP rate limited (`_check_link_rate_limit`) — seven users in
    one test would trip the limiter. What is under test here is the notification
    fan-out, not the linking handshake, so the fixture takes the direct route.
    """
    stamp = f"{int(time.time() * 1000000)}_{tag}_{next(_telegram_seq)}"
    telegram_id = str(abs(hash(stamp)) % 10**9)
    resp = client.post(
        "/auth/register",
        json={"email": f"notif_{stamp}@example.com", "password": "testpass123"},
    )
    if resp.status_code != 200:
        pytest.skip("Database not available for notification test")
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = int(client.get("/auth/me", headers=headers).json()["id"])
    api_shared.db_service.set_user_telegram_id(user_id, telegram_id)
    return headers, telegram_id


def _seeded_game(client: TestClient) -> tuple[str, int, list[tuple[dict, str]]]:
    """A game with all seven powers held by real users with numeric telegram_ids.

    Returns ``(game_id, numeric_row_id, [(headers, telegram_id), ...])`` ordered to
    match ``REQUIRED_POWERS``.
    """
    creator_headers, creator_tg = _register(client, "creator")
    resp = client.post(
        "/games/create",
        json={"map_name": "standard", "initial_phase": "Movement"},
        headers=creator_headers,
    )
    assert resp.status_code == 200, resp.text
    game_id = resp.json()["game_id"]

    users = [(creator_headers, creator_tg)]
    for power in REQUIRED_POWERS[1:]:
        users.append(_register(client, power))

    for power, (headers, telegram_id) in zip(REQUIRED_POWERS, users):
        resp = client.post(
            f"/games/{game_id}/join",
            json={"game_id": int(game_id), "power": power, "telegram_id": telegram_id},
            headers=headers,
        )
        assert resp.status_code == 200, f"join {power}: {resp.text}"

    listing = client.get("/games").json()["games"]
    row_id = next(int(g["id"]) for g in listing if str(g["game_id"]) == str(game_id))
    return str(game_id), row_id, users


def _recipients(mock: Any) -> set[str]:
    """The telegram_ids a patched `requests.post` was asked to notify."""
    found = set()
    for call in mock.call_args_list:
        payload = call.kwargs.get("json") or {}
        if "telegram_id" in payload:
            found.add(str(payload["telegram_id"]))
    return found


@pytest.mark.integration
@pytest.mark.database
def test_manual_and_deadline_triggers_notify_the_same_players() -> None:
    """The whole point of G3: the two triggers must not disagree about recipients."""
    client = TestClient(app)

    # --- manual trigger -------------------------------------------------
    game_id, _row_id, users = _seeded_game(client)
    caller_headers, caller_tg = users[0]
    with patch("server.api.shared.requests.post") as mock_post:
        resp = client.post(f"/games/{game_id}/process_turn", headers=caller_headers)
        assert resp.status_code == 200, resp.text
        manual_recipients = _recipients(mock_post)

    all_telegram_ids = {tg for _h, tg in users}
    # Every player except whoever pressed the button; they have the resolution
    # in the HTTP response they just received.
    assert manual_recipients == all_telegram_ids - {caller_tg}, (
        "manual process_turn notified the wrong set of players"
    )
    assert caller_tg not in manual_recipients, "the caller was notified twice"

    # --- deadline trigger, fresh game, same shape ------------------------
    game_id2, row_id2, users2 = _seeded_game(client)
    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)).isoformat()
    resp = client.post(
        f"/games/{game_id2}/deadline", json={"deadline": past}, headers=users2[0][0]
    )
    assert resp.status_code == 200, resp.text

    with patch("server.api.shared.requests.post") as mock_post:
        process_due_deadlines(datetime.datetime.now(datetime.timezone.utc))
        deadline_recipients = _recipients(mock_post)

    all_telegram_ids2 = {tg for _h, tg in users2}
    # Nobody triggered this one, so nobody is excluded.
    assert deadline_recipients == all_telegram_ids2, (
        "deadline processing notified the wrong set of players"
    )

    # The comparison that would have caught the original drift: both triggers
    # reach the same *proportion* of the table — everyone who didn't cause it.
    assert len(deadline_recipients) == len(manual_recipients) + 1
    assert len(manual_recipients) == 6


@pytest.mark.integration
@pytest.mark.database
def test_manual_trigger_notifies_the_ordinary_case_not_only_game_end() -> None:
    """The specific regression: an ordinary processed turn used to notify nobody.

    `routes/games.py` only called `notify_players` inside its
    `status == "COMPLETED"` branch, so a mid-game turn was silent. A fresh game is
    nowhere near ending, so any notification here proves the ordinary path fires.
    """
    client = TestClient(app)
    game_id, _row_id, users = _seeded_game(client)
    with patch("server.api.shared.requests.post") as mock_post:
        resp = client.post(f"/games/{game_id}/process_turn", headers=users[0][0])
        assert resp.status_code == 200, resp.text
        recipients = _recipients(mock_post)

    assert resp.json()["game_status"] != "COMPLETED", "fixture game ended unexpectedly"
    assert recipients, "an ordinary processed turn notified nobody (the G3 bug)"
    messages = [
        (c.kwargs.get("json") or {}).get("message", "") for c in mock_post.call_args_list
    ]
    assert any("processed" in m for m in messages), messages
    assert not any("has ended" in m for m in messages), (
        "a mid-game turn should not claim the game ended"
    )


@pytest.mark.integration
@pytest.mark.database
def test_reminder_flag_is_reset_by_both_triggers() -> None:
    """A new turn must re-arm the 10-minute reminder, whichever trigger ran.

    The deadline path did this (`reminder_sent[id] = False`); the manual path did
    not, so a game processed by hand never sent another deadline reminder for the
    rest of its life. Now both go through `notify_turn_processed`.
    """
    client = TestClient(app)
    game_id, row_id, users = _seeded_game(client)

    api_shared.reminder_sent[row_id] = True
    with patch("server.api.shared.requests.post"):
        resp = client.post(f"/games/{game_id}/process_turn", headers=users[0][0])
    assert resp.status_code == 200, resp.text
    assert api_shared.reminder_sent.get(row_id) is False, (
        "manual process_turn left the reminder flag set, suppressing every future reminder"
    )


@pytest.mark.integration
@pytest.mark.database
def test_notification_failure_does_not_fail_the_turn() -> None:
    """A Telegram outage must never fail a turn already committed to Postgres."""
    client = TestClient(app)
    game_id, _row_id, users = _seeded_game(client)
    before = client.get(f"/games/{game_id}/state").json()["phase"]

    with patch("server.api.shared.requests.post", side_effect=OSError("telegram down")):
        resp = client.post(f"/games/{game_id}/process_turn", headers=users[0][0])

    assert resp.status_code == 200, resp.text
    after = client.get(f"/games/{game_id}/state").json()["phase"]
    assert after != before, "the turn did not advance despite returning 200"
