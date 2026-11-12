"""DH3: a deadline is spent in the same locked write as the phase change.

``GameRepo.save_state`` used to move the phase in one commit and leave the
deadline for ``finish_processed_turn`` to spend in a later one. Between the
two, the row said "new phase, deadline already past", and the deadline
scheduler processed the new phase, which nobody had ordered for (#406).
Now ``_write_state`` clears ``deadline`` and ``reminded_deadline`` with the
phase; ``finish_processed_turn`` only arms the next one, and is told whether
the processed phase had one (``process_turn``'s ``deadline_spent``) for the
"No deadline is set for ..." notice.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from server.api.shared import db_service, game_service
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_auto_process import BOT, _table
from tests.test_deadline_scheduler_guards import DEADLINE, _deadline, _due_game, _phase, _rows, _tick
from tests.test_empty_phase_runs_at_once import _dislodge, _fail_second_process, _trap_board

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

NO_DEADLINE = "No deadline is set for Fall 1901 movement. To set one, use /deadline {g} <hours> (or /deadline {g} schedule ...)."


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_a_spent_deadline_does_not_process_the_phase_after_it(client: TestClient) -> None:
    game_id = _due_game(client)  # S1901M, deadline due
    # The manual route / auto-process commits the turn (first of its writes) ...
    game_service.process_turn(game_id, expected_phase_code="S1901M")
    assert _phase(game_id) == "F1901M"
    # ... and the scheduler ticks before finish_processed_turn runs.
    spy = _tick(DEADLINE + timedelta(seconds=1), _rows(game_id))
    assert spy.call_count == 0, "the scheduler processed F1901M on S1901M's deadline"
    assert _phase(game_id) == "F1901M"


def test_the_phase_change_spends_the_deadline_and_its_reminder(client: TestClient) -> None:
    game_id = _due_game(client)
    assert db_service.claim_deadline_reminder(int(game_id), DEADLINE) is True
    assert db_service.get_game_by_game_id(game_id).reminded_deadline is not None
    result = game_service.process_turn(game_id, expected_phase_code="S1901M")
    assert result["deadline_spent"] is True
    row = db_service.get_game_by_game_id(game_id)
    assert (row.phase_code, row.deadline, row.reminded_deadline) == ("F1901M", None, None)
    # The next phase had none to spend.
    assert game_service.process_turn(game_id, expected_phase_code="F1901M")["deadline_spent"] is False


def test_a_deadline_set_for_the_new_phase_before_the_turn_is_finished_is_kept(client: TestClient) -> None:
    game_id = _due_game(client)
    result = game_service.process_turn(game_id, expected_phase_code="S1901M")
    # Someone sets F1901M's deadline before the processing path finishes the turn.
    new = DEADLINE + timedelta(days=3)
    db_service.update_game_deadline(int(game_id), new)
    api_shared.after_turn_processed(
        game_id,
        int(game_id),
        prev_phase_code="S1901M",
        trigger="manual",
        had_deadline=result["deadline_spent"],
    )
    assert _deadline(game_id) == new


def test_a_folded_phase_still_says_the_spent_deadline_is_gone(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BV2: the movement's deadline is spent before the empty retreat is folded
    in, and the DM of the phase that needs the players still says it is gone."""
    game_id, e, f = _table(client, auto=False)
    _trap_board(game_id)
    _dislodge(client, game_id, e, f)
    db_service.update_game_deadline(int(game_id), datetime.now(timezone.utc) + timedelta(hours=1))
    monkeypatch.setattr(api_shared, "scheduled_deadline", lambda _gid, now=None: None)
    with OutboxProbe() as probe:
        resp = client.post(f"/games/{game_id}/process_turn", headers=BOT)
    assert resp.status_code == 200, resp.text
    assert _phase(game_id) == "F1901M"
    assert _deadline(game_id) is None
    assert probe.by_recipient()[f] == [
        f"The turn has been processed for game {game_id}. Orders are due for Fall 1901 movement.\n"
        "Your results for Spring 1901 movement:\nA BEL was dislodged by A PIC (ENGLAND).\nA PAR held.\n"
        "Your A BEL was dislodged and has nowhere to retreat: it is disbanded, no order needed.\n"
        "\n" + NO_DEADLINE.format(g=game_id)
    ]


def test_a_failing_folded_phase_gets_its_deadline_armed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The empty phase that fails to process is left with the deadline a new
    phase gets: the spent one is gone with the phase change, and the folded
    call armed none."""
    game_id, e, f = _table(client, auto=False)
    _trap_board(game_id)
    _dislodge(client, game_id, e, f)
    db_service.update_game_deadline(int(game_id), datetime.now(timezone.utc) + timedelta(hours=1))
    slot = datetime(2031, 3, 3, 16, 0)
    monkeypatch.setattr(api_shared, "scheduled_deadline", lambda _gid, now=None: slot)
    assert _fail_second_process(monkeypatch, {game_id}) == []
    resp = client.post(f"/games/{game_id}/process_turn", headers=BOT)
    assert resp.status_code == 200, resp.text
    assert (_phase(game_id), _deadline(game_id)) == ("S1901R", slot)
