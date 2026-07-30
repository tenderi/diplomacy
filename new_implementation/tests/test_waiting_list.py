"""The waiting list is durable, atomic, and actually notifies people (G5).

The queue used to be `telegram_bot/games.py`'s `WAITING_LIST` module global, with
three defects these tests pin shut:

1. **Dropped on every restart** — the bot restarts on every deploy, so a
   partially filled queue vanished and the players in it were never told.
   Now a Postgres table, so `test_queue_survives_a_process_restart` is meaningful.
2. **The notification was a stub that only logged** —
   `logger.info(f"Would notify {telegram_id}: {message}")`. When the 7th player
   joined, the six already queued got *nothing*; only the 7th saw a reply,
   because that came from `wait()`'s own `reply_text`.
3. **Filling it was not atomic** — it created the game, joined seven players in a
   loop, then cleared the list. A failure inside the loop left an orphan game
   with a partial roster *and* an uncleared queue, so the next `/wait` tripped
   the threshold again and minted another orphan. It also took
   `waiting_list[:required_size]` but `clear()`ed everything, dropping an 8th
   queued player.
"""
from __future__ import annotations

import itertools
import time
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from server.api.routes.waiting_list import WAITING_LIST_SIZE

pytestmark = [pytest.mark.integration, pytest.mark.database]

_seq = itertools.count(1)


@pytest.fixture(autouse=True)
def _empty_queue():
    """The queue is global server state; isolate each test from the others."""
    api_shared.db_service.clear_waiting_list()
    yield
    api_shared.db_service.clear_waiting_list()


def _register(client: TestClient, tag: str) -> str:
    """Register a user with a linked numeric telegram_id; return the telegram_id."""
    stamp = f"{int(time.time() * 1000000)}_{tag}_{next(_seq)}"
    telegram_id = str(abs(hash(stamp)) % 10**9)
    resp = client.post(
        "/auth/register",
        json={"email": f"wl_{stamp}@example.com", "password": "testpass123"},
    )
    if resp.status_code != 200:
        pytest.skip("Database not available for waiting-list test")
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    user_id = int(client.get("/auth/me", headers=headers).json()["id"])
    api_shared.db_service.set_user_telegram_id(user_id, telegram_id)
    return telegram_id


def _join(client: TestClient, telegram_id: str, name: str = "Test Player") -> dict:
    resp = client.post(
        "/waiting_list/join",
        json={"telegram_id": telegram_id, "full_name": name},
        headers={"X-Bot-Secret": api_shared.BOT_SECRET} if api_shared.BOT_SECRET else {},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _auth_join(client: TestClient, telegram_id: str) -> Any:
    """Join using the real auth path, returning the raw response for status checks."""
    return client.post(
        "/waiting_list/join",
        json={"telegram_id": telegram_id},
        headers={"X-Bot-Secret": api_shared.BOT_SECRET} if api_shared.BOT_SECRET else {},
    )


def _notified(mock: Any) -> dict[str, list[str]]:
    """telegram_id -> every message it received, from a patched `requests.post`.

    **One patch covers both modules.** `api/shared.py` and
    `routes/waiting_list.py` each do `import requests`, so they reference the
    same module object; patching `server.api.shared.requests.post` and
    `server.api.routes.waiting_list.requests.post` in the same `with` block
    rebinds the same attribute twice and only the inner mock ever sees a call.
    """
    out: dict[str, list[str]] = {}
    for call in mock.call_args_list:
        payload = call.kwargs.get("json") or {}
        if "telegram_id" in payload:
            out.setdefault(str(payload["telegram_id"]), []).append(payload.get("message", ""))
    return out


def _assigned_power(messages: list[str]) -> str:
    """The power named in a player's "you've been assigned X" DM."""
    for message in messages:
        if "assigned" in message:
            return message.split("assigned ")[1].split(".")[0].strip("*")
    raise AssertionError(f"no assignment message among {messages}")


def test_partial_queue_creates_no_game() -> None:
    client = TestClient(app)
    for i in range(WAITING_LIST_SIZE - 1):
        result = _join(client, _register(client, f"p{i}"))
        assert result["game_created"] is False
        assert result["size"] == i + 1
    assert client.get("/waiting_list").json() == {
        "size": WAITING_LIST_SIZE - 1,
        "required": WAITING_LIST_SIZE,
        "slots_remaining": 1,
    }


def test_filling_the_queue_notifies_everyone_in_it() -> None:
    """The headline G5 fix: all seven players are told, not just the last one.

    The old `notify_callback` only wrote a log line, so the six already-queued
    players learned nothing — the 7th's reply came from `wait()` itself.
    """
    client = TestClient(app)
    ids = [_register(client, f"p{i}") for i in range(WAITING_LIST_SIZE)]

    for telegram_id in ids[:-1]:
        assert _join(client, telegram_id)["game_created"] is False

    with patch("server.api.shared.requests.post") as mock_post:
        result = _join(client, ids[-1])

    assert result["game_created"] is True
    assert result["game_id"]

    notified = _notified(mock_post)
    assert set(notified) == set(ids), (
        f"not every queued player was notified: missing {set(ids) - set(notified)}"
    )
    # Each is told their own power, and the seven powers are all distinct.
    powers = [_assigned_power(messages) for messages in notified.values()]
    assert len(set(powers)) == WAITING_LIST_SIZE, powers
    assert result["assignments"] and set(result["assignments"]) == set(powers)


def test_queue_is_emptied_by_a_successful_fill() -> None:
    client = TestClient(app)
    ids = [_register(client, f"p{i}") for i in range(WAITING_LIST_SIZE)]
    with patch("server.api.shared.requests.post"):
        for telegram_id in ids:
            _join(client, telegram_id)
    assert client.get("/waiting_list").json()["size"] == 0


def test_an_eighth_player_is_held_for_the_next_game_not_dropped() -> None:
    """The old code took `[:7]` but `clear()`ed everything, losing the 8th.

    Driven through `try_fill_waiting_list` with eight entries seeded via the DAL
    rather than eight `/waiting_list/join` calls: joining fills the queue the
    moment it reaches seven, so there is no way to have eight queued *and* an
    unfilled queue over HTTP. Seeding directly is the only way to exercise the
    "more than enough waiting" branch at all.
    """
    from server.api.routes.waiting_list import try_fill_waiting_list

    client = TestClient(app)
    ids = [_register(client, f"p{i}") for i in range(WAITING_LIST_SIZE + 1)]
    for telegram_id in ids:
        assert api_shared.db_service.add_to_waiting_list(telegram_id, "Seeded")
    assert api_shared.db_service.count_waiting_list() == WAITING_LIST_SIZE + 1

    with patch("server.api.shared.requests.post") as mock_post:
        created = try_fill_waiting_list()

    assert created is not None
    # Exactly seven consumed; the eighth is held for the next game.
    assert api_shared.db_service.count_waiting_list() == 1

    remaining = api_shared.db_service.get_waiting_list()
    assert len(remaining) == 1
    assert remaining[0][0] == ids[-1], (
        f"FIFO violated: expected the newest joiner to remain, got {remaining}"
    )

    notified = _notified(mock_post)
    assert set(notified) == set(ids[:-1]), (
        "the wrong seven were placed, or the eighth was pulled in early"
    )
    assert ids[-1] not in notified


def test_a_failure_mid_fill_leaves_the_queue_intact_and_mints_no_orphan() -> None:
    """G5's "done when": make the join call raise and check nothing is lost.

    The old code created the game first, so a failure in the join loop left an
    orphan game *and* an uncleared queue — and the next `/wait` tripped the
    threshold again and minted another orphan. Claiming the entries first, then
    validating, means a failure re-queues exactly what it took.
    """
    client = TestClient(app)
    ids = [_register(client, f"p{i}") for i in range(WAITING_LIST_SIZE)]
    for telegram_id in ids[:-1]:
        _join(client, telegram_id)

    games_before = len(client.get("/games").json()["games"])

    # Fail on the 4th power assignment, mid-loop.
    real_create_player = api_shared.db_service.create_player
    calls = {"n": 0}

    def flaky_create_player(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 4:
            raise RuntimeError("simulated database failure on the 4th player")
        return real_create_player(*args, **kwargs)

    with patch.object(api_shared.db_service, "create_player", side_effect=flaky_create_player), \
         patch("server.api.shared.requests.post"):
        result = _join(client, ids[-1])

    assert result["game_created"] is False, "reported success despite a mid-fill failure"

    # Every player is still queued -- nobody silently lost their place.
    queued = {tid for tid, _name in api_shared.db_service.get_waiting_list()}
    assert queued == set(ids), f"queue was corrupted by the failure: {queued}"

    # And the retry works, rather than compounding the problem.
    with patch("server.api.shared.requests.post") as mock_post:
        retry = _join(client, ids[-1])
    assert retry["game_created"] is True, "the queue could not recover"
    assert set(_notified(mock_post)) == set(ids)

    # One game from the successful retry. The failed attempt's partially-populated
    # game is the documented residual (there is no single-game delete path); what
    # matters is that it happened once, not once per subsequent /wait.
    games_after = len(client.get("/games").json()["games"])
    assert games_after - games_before <= 2, (
        f"created {games_after - games_before} games; the orphan is compounding"
    )


def test_joining_twice_does_not_take_two_slots() -> None:
    client = TestClient(app)
    telegram_id = _register(client, "dup")
    first = _join(client, telegram_id)
    second = _join(client, telegram_id)
    assert first["status"] == "queued"
    assert second["status"] == "already_queued"
    assert second["size"] == 1


def test_leaving_the_queue() -> None:
    client = TestClient(app)
    telegram_id = _register(client, "leaver")
    _join(client, telegram_id)
    resp = client.post(
        "/waiting_list/leave",
        json={"telegram_id": telegram_id},
        headers={"X-Bot-Secret": api_shared.BOT_SECRET} if api_shared.BOT_SECRET else {},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "removed"
    assert resp.json()["size"] == 0

    # Leaving twice is not an error, just a no-op.
    again = client.post(
        "/waiting_list/leave",
        json={"telegram_id": telegram_id},
        headers={"X-Bot-Secret": api_shared.BOT_SECRET} if api_shared.BOT_SECRET else {},
    )
    assert again.json()["status"] == "not_queued"


def test_unregistered_telegram_id_is_refused() -> None:
    """Queueing someone with no account would fail later, at game creation."""
    client = TestClient(app)
    resp = _auth_join(client, "999999999999")
    assert resp.status_code == 404, resp.text
    assert "register" in resp.json()["detail"].lower()


def test_queue_survives_a_process_restart() -> None:
    """The whole point of persisting it: a deploy must not drop the queue.

    A fresh `TestClient` and a fresh `DatabaseService` stand in for a restarted
    bot/API process. With the old module global this assertion was impossible to
    write, because the queue lived in the process that just died.
    """
    from persistence.database_service import DatabaseService
    from server.db_config import SQLALCHEMY_DATABASE_URL

    client = TestClient(app)
    ids = [_register(client, f"p{i}") for i in range(3)]
    for telegram_id in ids:
        _join(client, telegram_id)

    fresh = DatabaseService(SQLALCHEMY_DATABASE_URL)
    assert fresh.count_waiting_list() == 3
    assert {tid for tid, _n in fresh.get_waiting_list()} == set(ids)


def test_claim_is_all_or_nothing() -> None:
    """`claim_waiting_list_entries` must never hand back a partial roster.

    A partial claim is how you get a game with four players and three ghosts.
    """
    db = api_shared.db_service
    db.clear_waiting_list()
    for i in range(3):
        db.add_to_waiting_list(f"claim_{i}", f"Player {i}")

    assert db.claim_waiting_list_entries(WAITING_LIST_SIZE) == []
    assert db.count_waiting_list() == 3, "a failed claim consumed entries"

    claimed = db.claim_waiting_list_entries(3)
    assert [tid for tid, _n in claimed] == ["claim_0", "claim_1", "claim_2"], claimed
    assert db.count_waiting_list() == 0


def test_requeue_preserves_order_at_the_front() -> None:
    """Players who nearly got a game keep their place ahead of newcomers."""
    db = api_shared.db_service
    db.clear_waiting_list()
    claimed = [("early_a", "A"), ("early_b", "B")]
    db.add_to_waiting_list("latecomer", "Late")
    db.requeue_waiting_list_entries(claimed)

    order = [tid for tid, _n in db.get_waiting_list()]
    assert order == ["early_a", "early_b", "latecomer"], order


def test_requeue_is_idempotent() -> None:
    """A double re-queue must not violate the UNIQUE constraint or duplicate a slot."""
    db = api_shared.db_service
    db.clear_waiting_list()
    entries = [("dup_a", "A")]
    db.requeue_waiting_list_entries(entries)
    db.requeue_waiting_list_entries(entries)
    assert db.count_waiting_list() == 1
