"""Track BH2: the deadline scheduler's and replace-power's guard branches.

- A deadline whose processing raises is still spent: a weekly schedule moves it
  to the next slot, so the next scheduler tick does not retry the broken game.
- The deadline-proposal expiry sweep reads a naive ``vote_deadline`` as UTC,
  leaves a not-yet-expired one alone, and does not clear a proposal that
  changed since the sweep read it.
- Deadline-proposal errors name what is wrong: a missing game, a withdraw with
  nothing pending, a withdraw by someone other than the proposer.
- ``/replace`` refuses a held seat and an active seat, and the player who loses
  the race for a vacant seat gets a 409.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from persistence.database_service import DeadlineProposalChange
from server.api import app
from server.api import shared as api_shared
from server.api.shared import db_service, game_service
from server.deadline_schedule import parse_schedule
from tests.conftest import _get_db_url
from tests.test_auto_process import _table
from tests.test_quit_and_replace import _as, _game_with_france, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

DAILY = "Mon,Tue,Wed,Thu,Fri,Sat,Sun 12:00"
MISSING = "987654321"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _stored_deadline(game_id: str) -> Optional[datetime]:
    deadline = db_service.get_game_by_game_id(game_id).deadline
    return None if deadline is None else deadline.replace(tzinfo=timezone.utc)


class TestFailedDeadlineIsSpent:
    def test_a_scheduled_deadline_that_fails_to_process_moves_to_the_next_slot(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        game_id, e, _f = _table(client, auto=False)
        resp = client.post(f"/games/{game_id}/deadline/schedule", json=_as(e, schedule=DAILY))
        assert resp.status_code == 200, resp.text
        db_service.update_game_deadline(int(game_id), datetime.now(timezone.utc) - timedelta(minutes=1))
        process = Mock(side_effect=RuntimeError("adjudicator exploded"))
        monkeypatch.setattr(game_service, "process_turn", process)

        now = datetime.now(timezone.utc)
        api_shared.process_due_deadlines(now)
        api_shared.process_due_deadlines(now + timedelta(seconds=1))

        # Other tests' games share the database and may be due too: count only this one.
        assert [c.args[0] for c in process.call_args_list].count(str(game_id)) == 1  # the second tick found nothing due
        schedule = parse_schedule(DAILY, "UTC")
        expected = {schedule.next_deadline(now), schedule.next_deadline(now + timedelta(seconds=5))}
        assert _stored_deadline(game_id) in expected
        assert client.get(f"/games/{game_id}/state").json()["phase"] == "S1901M"


def _proposal(client: TestClient, game_id: str, tg: str, power: str, **extra: Any) -> Dict[str, Any]:
    resp = client.post(f"/games/{game_id}/deadline/propose", json=_as(tg, power=power, hours=5.0, **extra))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _set_vote_deadline(game_id: str, raw: str) -> None:
    def rewrite(current: Optional[Dict[str, Any]]) -> DeadlineProposalChange:
        assert current is not None
        return DeadlineProposalChange({**current, "vote_deadline": raw}, {})

    db_service.modify_deadline_proposal(game_id, rewrite)


def _pending(client: TestClient, game_id: str) -> Optional[Dict[str, Any]]:
    return client.get(f"/games/{game_id}/deadline").json()["pending_proposal"]


class TestProposalExpiry:
    def test_a_naive_vote_deadline_in_the_past_is_read_as_utc_and_expires(self, client: TestClient) -> None:
        game_id, e, _f = _table(client, auto=False)
        _proposal(client, game_id, e, "ENGLAND", vote_hours=1.0)
        _set_vote_deadline(game_id, "2020-01-01T00:00:00")
        api_shared.expire_deadline_proposals(datetime.now(timezone.utc))
        assert _pending(client, game_id) is None

    def test_a_naive_vote_deadline_in_the_future_is_left_alone(self, client: TestClient) -> None:
        game_id, e, _f = _table(client, auto=False)
        _proposal(client, game_id, e, "ENGLAND", vote_hours=1.0)
        _set_vote_deadline(game_id, "2999-01-01T00:00:00")
        api_shared.expire_deadline_proposals(datetime.now(timezone.utc))
        assert _pending(client, game_id)["vote_deadline"] == "2999-01-01T00:00:00"

    def test_a_proposal_that_changed_since_the_sweep_read_it_is_kept(self, client: TestClient) -> None:
        game_id, e, _f = _table(client, auto=False)
        _proposal(client, game_id, e, "ENGLAND", vote_hours=1.0)
        stale = Mock(id=int(game_id), game_id=game_id, pending_deadline_proposal={
            "proposed_by": "ENGLAND", "vote_deadline": "2020-01-01T00:00:00+00:00", "votes": {},
        })
        with patch.object(db_service, "get_games_with_pending_deadline_proposals", return_value=[stale]), \
                patch.object(api_shared, "notify_players") as notify:
            api_shared.expire_deadline_proposals(datetime.now(timezone.utc))
        assert _pending(client, game_id)["proposed_by"] == "ENGLAND"
        notify.assert_not_called()


class TestDeadlineProposalErrors:
    def test_a_vote_in_a_missing_game_names_it(self) -> None:
        with pytest.raises(api_shared.DeadlineProposalError) as err:
            api_shared.vote_on_deadline_proposal(MISSING, int(MISSING), "FRANCE", True)
        assert str(err.value) == f"game {MISSING} not found"

    def test_a_game_gone_under_the_lock_is_a_proposal_error(self) -> None:
        with patch.object(game_service, "active_powers", return_value=frozenset({"FRANCE"})), \
                pytest.raises(api_shared.DeadlineProposalError) as err:
            api_shared.propose_deadline(MISSING, int(MISSING), "FRANCE", 5.0, None)
        assert str(err.value) == f"game {MISSING} not found"

    def test_a_withdraw_in_a_missing_game_is_a_proposal_error(self) -> None:
        with pytest.raises(api_shared.DeadlineProposalError) as err:
            api_shared.withdraw_deadline_proposal(MISSING, "FRANCE")
        assert str(err.value) == f"game {MISSING} not found"

    def test_the_withdraw_route_on_a_missing_game_is_404(self, client: TestClient) -> None:
        tg = _telegram_user(client, "nogame")
        resp = client.post(f"/games/{MISSING}/deadline/withdraw", json=_as(tg, power="FRANCE"))
        assert (resp.status_code, resp.json()["detail"]) == (404, f"Game {MISSING} not found")

    def test_withdrawing_with_nothing_pending_says_so(self, client: TestClient) -> None:
        game_id, e, _f = _table(client, auto=False)
        resp = client.post(f"/games/{game_id}/deadline/withdraw", json=_as(e, power="ENGLAND"))
        assert (resp.status_code, resp.json()["detail"]) == (
            400, f"No deadline proposal is pending in game {game_id}"
        )

    def test_only_the_proposer_may_withdraw_and_is_named(self, client: TestClient) -> None:
        game_id, e, f = _table(client, auto=False)
        _proposal(client, game_id, e, "ENGLAND")
        resp = client.post(f"/games/{game_id}/deadline/withdraw", json=_as(f, power="FRANCE"))
        assert (resp.status_code, resp.json()["detail"]) == (
            400, "Only ENGLAND, who proposed it, can withdraw it"
        )
        assert _pending(client, game_id)["proposed_by"] == "ENGLAND"


class TestReplaceGuards:
    def test_a_held_seat_is_refused(self, client: TestClient) -> None:
        game_id, _a = _game_with_france(client)
        b = _telegram_user(client, "intruder")
        resp = client.post(f"/games/{game_id}/replace", json=_as(b, power="FRANCE"))
        assert (resp.status_code, resp.json()["detail"]) == (
            400, "Power is already assigned to a user. Only unassigned, inactive powers can be replaced."
        )

    def test_an_unheld_but_active_seat_is_refused(self, client: TestClient) -> None:
        game_id, _a = _game_with_france(client)
        b = _telegram_user(client, "early")
        seat = Mock(id=1, user_id=None, is_active=True)
        with patch.object(db_service, "get_player_by_game_id_and_power", return_value=seat):
            resp = client.post(f"/games/{game_id}/replace", json=_as(b, power="FRANCE"))
        assert (resp.status_code, resp.json()["detail"]) == (
            400, "Power is not inactive and cannot be replaced. Only inactive/vacated powers can be replaced."
        )

    def test_losing_the_race_for_a_vacant_seat_is_409(self, client: TestClient) -> None:
        game_id, a = _game_with_france(client)
        assert client.post(f"/games/{game_id}/quit", json=_as(a)).status_code == 200
        vacant = db_service.get_player_by_game_id_and_power(game_id=game_id, power="FRANCE")
        b, c = _telegram_user(client, "first"), _telegram_user(client, "second")
        assert client.post(f"/games/{game_id}/replace", json=_as(b, power="FRANCE")).status_code == 200
        # c's checks read the seat before b's write landed.
        with patch.object(db_service, "get_player_by_game_id_and_power", return_value=vacant):
            resp = client.post(f"/games/{game_id}/replace", json=_as(c, power="FRANCE"))
        assert (resp.status_code, resp.json()["detail"]) == (409, "Someone else has just taken this power.")
        b_id = int(db_service.get_user_by_telegram_id(b).id)
        assert db_service.get_player_by_game_id_and_power(game_id=game_id, power="FRANCE").user_id == b_id
