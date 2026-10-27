"""The deadline scheduler's guards (BU3).

``process_due_deadlines`` is driven one iteration at a time, with an explicit
``now`` and no sleeps. The games it walks are this test's own rows, read from
the database (so their deadlines are the naive UTC values Postgres hands back):
the shared test database holds other tests' games, which may be due too.

- A naive deadline is read as UTC, and so is a naive ``now``: due at or after
  the deadline, not one second before it.
- A game deleted, or whose deadline was cleared, after the scheduler read it is
  skipped, and the games after it are still processed.
- A game whose processing raises has its deadline spent, and the next due game
  is still processed; a failure to list the games is logged, not raised.
- ``maybe_auto_process`` stops when the game is deleted between processing a
  phase and finishing it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from server.api.shared import db_service, game_service
from tests.conftest import _get_db_url
from tests.test_auto_process import _table

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

# A whole second, so the naive value round-trips through Postgres unchanged.
DEADLINE = datetime(2026, 10, 27, 12, 0, 0)  # naive UTC


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _due_game(client: TestClient, deadline: datetime = DEADLINE) -> str:
    """A full two-player table in S1901M with ``deadline`` stored."""
    game_id, _e, _f = _table(client, auto=False)
    db_service.update_game_deadline(int(game_id), deadline)
    return game_id


def _rows(*game_ids: str) -> list[Any]:
    return [db_service.get_game_by_game_id(g) for g in game_ids]


def _phase(game_id: str) -> str:
    return str(db_service.get_game_by_game_id(game_id).phase_code)


def _deadline(game_id: str) -> Optional[datetime]:
    deadline = db_service.get_game_by_game_id(game_id).deadline
    return None if deadline is None else deadline.replace(tzinfo=None)


def _tick(now: datetime, rows: list[Any], process_turn: Any = None) -> Mock:
    """One scheduler pass over ``rows``; returns the ``process_turn`` spy."""
    spy = Mock(side_effect=process_turn or game_service.process_turn)
    with (
        patch.object(db_service, "get_games_with_deadlines_and_active_status", return_value=rows),
        patch.object(game_service, "process_turn", spy),
    ):
        api_shared.process_due_deadlines(now)
    return spy


class TestDue:
    def test_the_stored_deadline_is_naive(self, client: TestClient) -> None:
        game_id = _due_game(client)
        assert db_service.get_game_by_game_id(game_id).deadline == DEADLINE

    @pytest.mark.parametrize("now", [DEADLINE, DEADLINE + timedelta(seconds=1)], ids=["at", "after"])
    def test_a_naive_deadline_at_or_before_a_naive_now_is_processed(self, client: TestClient, now: datetime) -> None:
        game_id = _due_game(client)
        spy = _tick(now, _rows(game_id))
        assert [c.args[0] for c in spy.call_args_list] == [game_id]
        assert spy.call_args.kwargs == {"expected_phase_code": "S1901M"}
        assert _phase(game_id) == "F1901M"
        assert _deadline(game_id) is None  # spent; nothing re-arms it

    def test_a_naive_deadline_before_an_aware_now_in_another_zone_is_processed(self, client: TestClient) -> None:
        game_id = _due_game(client)
        # 14:00 at UTC+2 is 12:00 UTC: the same instant as the deadline.
        now = DEADLINE.replace(hour=14, tzinfo=timezone(timedelta(hours=2)))
        _tick(now, _rows(game_id))
        assert _phase(game_id) == "F1901M"

    @pytest.mark.parametrize(
        "now",
        [DEADLINE - timedelta(seconds=1), (DEADLINE - timedelta(seconds=1)).replace(tzinfo=timezone.utc)],
        ids=["naive", "aware"],
    )
    def test_a_deadline_one_second_ahead_is_not_processed(self, client: TestClient, now: datetime) -> None:
        game_id = _due_game(client)
        spy = _tick(now, _rows(game_id))
        assert spy.call_count == 0
        assert _phase(game_id) == "S1901M"
        assert _deadline(game_id) == DEADLINE


class TestChangedMidLoop:
    def test_a_game_deleted_mid_loop_is_skipped_and_the_next_is_processed(self, client: TestClient) -> None:
        first, gone, last = _due_game(client), _due_game(client), _due_game(client)
        rows = _rows(first, gone, last)
        real = game_service.process_turn

        def process_turn(game_id: str, **kwargs: Any) -> Any:
            if game_id == first:  # another request deletes ``gone`` while ``first`` is processed
                assert db_service.delete_game(int(gone)) is True
            return real(game_id, **kwargs)

        spy = _tick(DEADLINE + timedelta(minutes=1), rows, process_turn)
        assert [c.args[0] for c in spy.call_args_list] == [first, last]
        assert db_service.get_game_by_game_id(gone) is None
        assert (_phase(first), _phase(last)) == ("F1901M", "F1901M")

    def test_a_deadline_cleared_after_the_read_is_skipped_and_the_next_is_processed(self, client: TestClient) -> None:
        cleared, last = _due_game(client), _due_game(client)
        rows = _rows(cleared, last)  # the scheduler's read, deadlines still set
        db_service.update_game_deadline(int(cleared), None)
        spy = _tick(DEADLINE + timedelta(minutes=1), rows)
        assert [c.args[0] for c in spy.call_args_list] == [last]
        assert (_phase(cleared), _deadline(cleared)) == ("S1901M", None)
        assert _phase(last) == "F1901M"


class TestFailures:
    def test_one_game_raising_does_not_stop_the_next(self, client: TestClient) -> None:
        broken, fine = _due_game(client), _due_game(client)
        real = game_service.process_turn

        def process_turn(game_id: str, **kwargs: Any) -> Any:
            if game_id == broken:
                raise RuntimeError("adjudicator exploded")
            return real(game_id, **kwargs)

        spy = _tick(DEADLINE + timedelta(minutes=1), _rows(broken, fine), process_turn)
        assert [c.args[0] for c in spy.call_args_list] == [broken, fine]
        # The broken game's deadline is spent (no schedule: cleared), its board untouched.
        assert (_phase(broken), _deadline(broken)) == ("S1901M", None)
        assert (_phase(fine), _deadline(fine)) == ("F1901M", None)

    def test_a_failure_to_list_the_games_is_logged_not_raised(self, caplog: pytest.LogCaptureFixture) -> None:
        listing = Mock(side_effect=RuntimeError("database went away"))
        with patch.object(db_service, "get_games_with_deadlines_and_active_status", listing):
            assert api_shared.process_due_deadlines(DEADLINE) is None
        assert listing.call_count == 1
        assert [r.getMessage() for r in caplog.records if r.name == api_shared.scheduler_logger.name] == [
            "Error processing deadlines"
        ]


class TestAutoProcessDeleted:
    def test_a_game_deleted_after_its_phase_is_processed_is_not_finished(self, client: TestClient) -> None:
        game_id, _e, _f = _table(client, auto=True)
        real = game_service.process_turn

        def process_then_delete(gid: str, **kwargs: Any) -> Any:
            result = real(gid, **kwargs)
            assert db_service.delete_game(int(gid)) is True
            return result

        finish = Mock()
        with (
            patch.object(game_service, "ready_to_auto_process", return_value=True),
            patch.object(game_service, "process_turn", side_effect=process_then_delete) as process,
            patch.object(api_shared, "finish_processed_turn", finish),
        ):
            assert api_shared.maybe_auto_process(game_id) == 1
        assert process.call_count == 1
        assert finish.call_count == 0
        assert db_service.get_game_by_game_id(game_id) is None
