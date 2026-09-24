"""The bot's two background loops (``notifications.py``): whatever one tick does, the
loop keeps going and keeps its heartbeat fresh -- a dead loop means players stop
hearing about turns, or their queued orders are never sent."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from telegram.error import Forbidden, TimedOut

from server.telegram_bot import notifications
from server.telegram_bot.outbox import reset_outbox_for_tests
from tests.reliability_helpers import delivered, rejected

pytestmark = pytest.mark.unit


class _Stop(Exception):
    pass


@pytest.fixture(autouse=True)
def heartbeat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "heartbeat"
    monkeypatch.setattr(notifications, "HEARTBEAT_PATH", path)
    return path


def _ticks(n: int) -> AsyncMock:
    """An ``asyncio.sleep`` stand-in that ends the loop after ``n`` ticks."""
    count = {"n": 0}

    async def sleep(_seconds: float) -> None:
        count["n"] += 1
        if count["n"] >= n:
            raise _Stop

    return AsyncMock(side_effect=sleep)


def test_the_notification_loop_survives_a_failing_poll(heartbeat: Path) -> None:
    deliver = AsyncMock(side_effect=[RuntimeError("API exploded"), None, None])
    with patch.object(notifications, "deliver_pending_notifications", new=deliver), \
         patch.object(notifications.asyncio, "sleep", new=_ticks(3)), \
         patch.object(notifications.logger, "error") as log:
        with pytest.raises(_Stop):
            asyncio.run(notifications.notification_loop(Mock()))
    assert deliver.await_count == 3
    assert "API exploded" in log.call_args[0][1].args[0]
    assert heartbeat.exists()


def test_the_replay_loop_survives_failures_and_purges_hourly(tmp_path: Path) -> None:
    outbox = reset_outbox_for_tests(tmp_path / "outbox.sqlite3")
    replay = AsyncMock(side_effect=[RuntimeError("boom")] + [[]] * 800)
    with patch.object(notifications, "replay_outbox", new=replay), \
         patch.object(outbox, "purge_finished", wraps=outbox.purge_finished) as purge, \
         patch.object(notifications.asyncio, "sleep", new=_ticks(721)):
        with pytest.raises(_Stop):
            asyncio.run(notifications.outbox_replay_loop(Mock()))
    assert replay.await_count == 721
    assert purge.call_count == 1  # at tick 720 (~1 h at 5 s)


def test_a_report_telegram_refuses_does_not_stop_the_replay(tmp_path: Path) -> None:
    reset_outbox_for_tests(tmp_path / "outbox.sqlite3")
    finished = [delivered(chat_id=1), rejected("Not your power", chat_id=2), delivered(chat_id=3)]
    bot = Mock()
    bot.send_message = AsyncMock(side_effect=[Forbidden("bot was blocked"), TimedOut(), None])
    with patch.object(notifications, "drain_outbox_once", return_value=finished):
        assert asyncio.run(notifications.replay_outbox(bot)) == finished
    assert [c.kwargs["chat_id"] for c in bot.send_message.call_args_list] == [1, 2, 3]
    assert bot.send_message.call_args_list[1].kwargs["text"].startswith("❌ Not delivered")


def test_stopping_cancels_both_loops(tmp_path: Path) -> None:
    reset_outbox_for_tests(tmp_path / "outbox.sqlite3")

    async def forever(_app: Any) -> None:
        await asyncio.Event().wait()

    async def lifecycle() -> list[asyncio.Task]:
        with patch.object(notifications, "notification_loop", new=forever), \
             patch.object(notifications, "outbox_replay_loop", new=forever):
            tasks = notifications.start_background_loops(Mock())
            await asyncio.sleep(0)
            await notifications.stop_background_loops(Mock())
        return tasks

    tasks = asyncio.run(lifecycle())
    assert [t.get_name() for t in tasks] == ["diplomacy-notifications", "diplomacy-outbox-replay"]
    assert all(t.cancelled() for t in tasks)
    assert notifications._tasks == []


def test_queue_says_when_the_server_is_down_and_counts_attempts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outbox = reset_outbox_for_tests(tmp_path / "outbox.sqlite3")
    entry = outbox.enqueue(chat_id=555, endpoint="/games/7/message", payload={}, description="message to ITALY")
    for _ in range(2):  # two failed sends: each is marked in flight, then retried
        outbox.mark_inflight(entry.id)
        outbox.mark_retry(entry.id, "ConnectionError")
    monkeypatch.setattr(notifications, "_api_reachable", False)
    update = Mock()
    update.effective_user = Mock(id=555)
    update.message.reply_text = AsyncMock()
    asyncio.run(notifications.queue_status(update, Mock()))
    text = update.message.reply_text.call_args[0][0]
    assert "⚠️ unreachable -- writes are being queued" in text
    assert "message to ITALY -- 2 attempts" in text
