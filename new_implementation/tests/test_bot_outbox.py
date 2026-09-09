"""The bot's durable outbox (``server/telegram_bot/outbox.py``).

Pure unit tests over a temporary SQLite file: no API, no Telegram, no Postgres.
The property under test is the one the whole split deployment rests on --
**a write, once enqueued, is never lost**: it survives a process restart, is
retried in order, and ends in exactly one of delivered/rejected with the
original send time preserved.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from server.telegram_bot import outbox as ob

pytestmark = pytest.mark.unit


@pytest.fixture
def box(tmp_path):
    outbox = ob.Outbox(tmp_path / "outbox.sqlite3")
    yield outbox
    outbox.close()


def test_enqueue_is_durable_and_pending(box, tmp_path):
    entry = box.enqueue(42, "/games/set_orders", {"orders": ["A PAR H"]}, "orders for game 1")
    assert entry.state == ob.PENDING
    assert entry.key and entry.created_at.tzinfo is not None

    # A fresh handle on the same file sees it: this is the restart case.
    reopened = ob.Outbox(tmp_path / "outbox.sqlite3")
    try:
        again = reopened.get(entry.id)
        assert again is not None and again.key == entry.key and again.payload == {"orders": ["A PAR H"]}
        assert reopened.count_pending() == 1
    finally:
        reopened.close()


def test_due_is_fifo_and_honours_backoff(box):
    first = box.enqueue(1, "/a", {}, "first")
    second = box.enqueue(1, "/b", {}, "second")
    third = box.enqueue(2, "/c", {}, "third")
    assert [e.id for e in box.due()] == [first.id, second.id, third.id]

    box.mark_inflight(first.id)
    now = datetime.now(timezone.utc)
    next_at = box.mark_retry(first.id, "ConnectionError", now=now)
    assert next_at == now + timedelta(seconds=ob.backoff_seconds(1))
    # Not due yet...
    assert [e.id for e in box.due(now=now)] == [second.id, third.id]
    # ...but due once the backoff elapses, and still first in line.
    assert [e.id for e in box.due(now=next_at)] == [first.id, second.id, third.id]


def test_backoff_grows_and_caps():
    assert [ob.backoff_seconds(n) for n in (1, 2, 3, 4, 5, 9)] == [5, 10, 20, 40, 60, 60]


def test_delivered_and_rejected_leave_the_queue_but_keep_history(box):
    a = box.enqueue(7, "/a", {}, "a")
    b = box.enqueue(7, "/b", {}, "b")
    box.mark_inflight(a.id)
    box.mark_delivered(a.id, {"status": "ok"})
    box.mark_inflight(b.id)
    box.mark_rejected(b.id, "Sender not in game")

    assert box.count_pending() == 0
    assert box.due() == []
    recent = box.recent(chat_id=7)
    assert [(e.id, e.state) for e in recent] == [(b.id, ob.REJECTED), (a.id, ob.DELIVERED)]
    assert recent[1].response == {"status": "ok"}
    assert recent[0].last_error == "Sender not in game"
    assert recent[0].attempts == 1


def test_inflight_entries_are_reset_on_restart(box, tmp_path):
    e = box.enqueue(1, "/a", {}, "a")
    box.mark_inflight(e.id)
    assert box.get(e.id).state == ob.INFLIGHT
    # Simulate a crash mid-attempt: a new process opens the file.
    reopened = ob.Outbox(tmp_path / "outbox.sqlite3")
    try:
        assert reopened.get(e.id).state == ob.PENDING
        assert reopened.get(e.id).next_attempt_at is None  # retried immediately
    finally:
        reopened.close()


def test_pending_is_scoped_per_chat(box):
    box.enqueue(1, "/a", {}, "mine")
    box.enqueue(2, "/a", {}, "theirs")
    assert [e.description for e in box.pending(chat_id=1)] == ["mine"]
    assert len(box.pending()) == 2


def test_purge_finished_keeps_recent_and_pending(box):
    old = box.enqueue(1, "/a", {}, "old")
    box.mark_delivered(old.id, {})
    # Backdate its finish.
    box._conn.execute(
        "UPDATE outbox SET finished_at = ? WHERE id = ?",
        ((datetime.now(timezone.utc) - timedelta(days=30)).isoformat(), old.id),
    )
    fresh = box.enqueue(1, "/a", {}, "fresh")
    box.mark_delivered(fresh.id, {})
    still_pending = box.enqueue(1, "/a", {}, "pending")
    assert box.purge_finished() == 1
    assert box.get(old.id) is None
    assert box.get(fresh.id) is not None
    assert box.get(still_pending.id).state == ob.PENDING


def test_sent_at_label_is_short_for_today(box):
    e = box.enqueue(1, "/a", {}, "a")
    label = e.sent_at_label()
    assert label.endswith(" UTC") and len(label) == len("14:02 UTC")


def test_user_games_cache_roundtrip(box):
    assert box.cached_user_games("u1") is None
    box.cache_user_games("u1", [{"game_id": "1", "power": "FRANCE"}])
    games, fetched_at = box.cached_user_games("u1")
    assert games == [{"game_id": "1", "power": "FRANCE"}]
    assert fetched_at.tzinfo is not None
    box.cache_user_games("u1", [])
    assert box.cached_user_games("u1")[0] == []


def test_get_outbox_uses_data_dir_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DIPLOMACY_BOT_DATA_DIR", str(tmp_path / "data"))
    box = ob.reset_outbox_for_tests()
    assert box.path == tmp_path / "data" / "outbox.sqlite3"
    assert box.path.exists()
