"""The API's background work, driven without a real clock or real DAIDE sockets:

- ``_notify_daide_processed`` must reach DAIDE clients from wherever a turn is
  processed -- an async route (a running loop), a sync route on a worker thread
  (auto-processing from ``POST /games/set_orders``: the connections live on the main
  loop), or a script with no loop at all.
- ``deadline_scheduler`` catches up on missed deadlines at startup, then checks
  deadlines, reminders and proposal expiry every tick, and housekeeps hourly.
"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.api import shared

pytestmark = pytest.mark.unit


class _FakeDaide:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, int]] = []

    async def notify_game_processed(self, game_id: str, *, resolved_phase: Any = None) -> None:
        self.calls.append((game_id, resolved_phase, threading.get_ident()))


@pytest.fixture
def daide(monkeypatch: pytest.MonkeyPatch) -> _FakeDaide:
    fake = _FakeDaide()
    monkeypatch.setattr(shared, "daide_server", fake)
    monkeypatch.setattr(shared, "main_loop", None)
    return fake


class TestDaideNotification:
    def test_from_an_async_route_it_is_scheduled_on_the_running_loop(self, daide: _FakeDaide) -> None:
        async def route() -> None:
            shared._notify_daide_processed("7", "S1901M")
            assert daide.calls == []  # scheduled, not awaited inline
            await asyncio.sleep(0)

        asyncio.run(route())
        assert [c[:2] for c in daide.calls] == [("7", "S1901M")]

    def test_from_a_worker_thread_it_runs_on_the_main_loop(self, daide: _FakeDaide, monkeypatch: pytest.MonkeyPatch) -> None:
        loop = asyncio.new_event_loop()
        loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
        loop_thread.start()
        monkeypatch.setattr(shared, "main_loop", loop)
        try:
            shared._notify_daide_processed("7", "F1901M")  # this test thread has no loop
            for _ in range(200):
                if daide.calls:
                    break
                threading.Event().wait(0.01)
        finally:
            loop.call_soon_threadsafe(loop.stop)
            loop_thread.join(timeout=2)
            loop.close()
        assert [c[:2] for c in daide.calls] == [("7", "F1901M")]
        assert daide.calls[0][2] == loop_thread.ident

    def test_with_no_loop_anywhere_it_runs_to_completion(self, daide: _FakeDaide) -> None:
        shared._notify_daide_processed("7", None)
        assert [c[:2] for c in daide.calls] == [("7", None)]

    def test_without_a_daide_server_nothing_happens(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shared, "daide_server", None)
        assert shared._notify_daide_processed("7", None) is None  # must not raise


class _Stop(Exception):
    pass


def test_the_scheduler_catches_up_then_checks_every_tick_and_housekeeps_hourly(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    ticks = shared._HOUSEKEEPING_EVERY_TICKS + 1
    sleeps = {"n": 0}

    async def fake_sleep(seconds: float) -> None:
        assert seconds == 30
        sleeps["n"] += 1
        if sleeps["n"] > ticks:
            raise _Stop

    for name in ("process_due_deadlines", "check_and_send_reminders", "expire_deadline_proposals", "run_housekeeping"):
        monkeypatch.setattr(shared, name, Mock(side_effect=lambda *a, _n=name: calls.append(_n)))
    with patch.object(shared.asyncio, "sleep", new=AsyncMock(side_effect=fake_sleep)):
        with pytest.raises(_Stop):
            asyncio.run(shared.deadline_scheduler())

    # Startup: missed deadlines and expired proposals first, before any sleeping.
    assert calls[:2] == ["process_due_deadlines", "expire_deadline_proposals"]
    per_tick = calls[2:]
    assert per_tick.count("process_due_deadlines") == ticks
    assert per_tick.count("check_and_send_reminders") == ticks
    assert per_tick.count("expire_deadline_proposals") == ticks
    assert per_tick.count("run_housekeeping") == 1  # once in the first 121 ticks (~1 h)


def test_housekeeping_failure_is_logged_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shared.db_service, "purge_delivered_bot_notifications", Mock(side_effect=RuntimeError("db gone")))
    with patch.object(shared.scheduler_logger, "error") as log:
        shared.run_housekeeping()
    assert "db gone" in log.call_args[0][0]


def test_a_proposal_with_an_unreadable_expiry_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    game = Mock(game_id="7", id=7, pending_deadline_proposal={"vote_deadline": "sometime soon", "proposed_by": "FRANCE"})
    monkeypatch.setattr(shared.db_service, "get_games_with_pending_deadline_proposals", Mock(return_value=[game]))
    clear = Mock()
    monkeypatch.setattr(shared.db_service, "set_pending_deadline_proposal", clear)
    shared.expire_deadline_proposals(datetime(2030, 1, 1, tzinfo=shared.pytz.UTC))
    clear.assert_not_called()
