"""W10: process a turn as soon as all orders are in, unless someone asked to wait.

Opt-in per game (``auto_process``). "All orders in" is ``orders_status`` with
nothing missing -- which already leaves out powers with nothing to order this
phase and civil-disorder dummies (W9). A wait flag ("I'm still negotiating")
holds auto-processing for the current phase only; it never stops a deadline.
Every trigger -- manual, deadline, auto -- finishes a turn through
``api.shared.finish_processed_turn``.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from server.api.shared import db_service, game_service
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_quit_and_replace import BOT_SECRET, _as, _register_and_login, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

BOT = {"X-Bot-Secret": BOT_SECRET}
# Five dummies leave a two-player table: ENGLAND and FRANCE.
DUMMIES = ["AUSTRIA", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _table(client: TestClient, auto: bool) -> tuple[str, str, str]:
    """A game where ``e`` holds ENGLAND and ``f`` holds FRANCE; the rest are dummies."""
    resp = client.post(
        "/games/create",
        json={"map_name": "standard", "dummy_powers": DUMMIES, "auto_process": auto},
        headers=_register_and_login(client, "auto"),
    )
    game_id = str(resp.json()["game_id"])
    e, f = _telegram_user(client, "eng"), _telegram_user(client, "fra")
    assert client.post(f"/games/{game_id}/join", json=_as(e, power="ENGLAND")).status_code == 200
    assert client.post(f"/games/{game_id}/join", json=_as(f, power="FRANCE")).status_code == 200
    return game_id, e, f


def _order(client: TestClient, game_id: str, tg: str, power: str, orders: list[str]) -> dict:
    resp = client.post("/games/set_orders", json=_as(tg, game_id=game_id, power=power, orders=orders))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _phase(client: TestClient, game_id: str) -> str:
    return client.get(f"/games/{game_id}/state").json()["phase"]


def test_off_by_default_all_orders_in_changes_nothing(client: TestClient) -> None:
    game_id, e, f = _table(client, auto=False)
    _order(client, game_id, e, "ENGLAND", ["F LON H"])
    assert _order(client, game_id, f, "FRANCE", ["A PAR H"])["auto_processed"] == 0
    assert _phase(client, game_id) == "S1901M"


def test_the_last_order_processes_the_turn(client: TestClient) -> None:
    game_id, e, f = _table(client, auto=True)
    assert _order(client, game_id, e, "ENGLAND", ["F LON - NTH"])["auto_processed"] == 0
    assert _phase(client, game_id) == "S1901M"
    with OutboxProbe() as probe:
        assert _order(client, game_id, f, "FRANCE", ["A PAR - BUR"])["auto_processed"] == 1
    state = client.get(f"/games/{game_id}/state").json()
    assert state["phase"] == "F1901M"
    assert any(u["location"] == "NTH" for u in state["units_by_power"]["ENGLAND"])
    # The same finish as every other trigger: both players told, a snapshot taken.
    assert {e, f} <= probe.recipients()
    assert db_service.get_game_snapshots_by_game_id(int(game_id))


def test_a_wait_flag_holds_it_and_lowering_it_processes(client: TestClient) -> None:
    game_id, e, f = _table(client, auto=True)
    raised = client.post(f"/games/{game_id}/wait", json=_as(e, power="ENGLAND"))
    assert raised.status_code == 200 and raised.json()["waiting"] == ["ENGLAND"]
    _order(client, game_id, e, "ENGLAND", ["F LON H"])
    assert _order(client, game_id, f, "FRANCE", ["A PAR H"])["auto_processed"] == 0
    status = client.get(f"/games/{game_id}/orders_status").json()
    assert status["missing"] == [] and status["waiting"] == ["ENGLAND"] and status["auto_process"] is True

    lowered = client.post(f"/games/{game_id}/wait", json=_as(e, power="ENGLAND", waiting=False))
    assert lowered.json()["auto_processed"] == 1
    assert _phase(client, game_id) == "F1901M"
    # The phase is gone, and so is every flag raised during it.
    assert client.get(f"/games/{game_id}/orders_status").json()["waiting"] == []


def test_a_wait_flag_never_stops_a_deadline(client: TestClient) -> None:
    game_id, e, _f = _table(client, auto=True)
    client.post(f"/games/{game_id}/wait", json=_as(e, power="ENGLAND"))
    db_service.update_game_deadline(int(game_id), datetime.now(timezone.utc) - timedelta(minutes=1))
    api_shared.process_due_deadlines(datetime.now(timezone.utc))
    assert _phase(client, game_id) == "F1901M"


def test_switching_it_on_processes_a_turn_that_is_already_complete(client: TestClient) -> None:
    game_id, e, f = _table(client, auto=False)
    _order(client, game_id, e, "ENGLAND", ["F LON H"])
    _order(client, game_id, f, "FRANCE", ["A PAR H"])
    resp = client.post(f"/games/{game_id}/auto_process", json=_as(f, enabled=True))
    assert resp.status_code == 200 and resp.json()["auto_processed"] == 1
    assert _phase(client, game_id) == "F1901M"


def test_only_players_toggle_it_and_only_your_own_flag(client: TestClient) -> None:
    game_id, e, _f = _table(client, auto=False)
    outsider = _telegram_user(client, "outsider")
    assert client.post(f"/games/{game_id}/auto_process", json=_as(outsider, enabled=True)).status_code == 403
    assert client.post(f"/games/{game_id}/wait", json=_as(e, power="FRANCE")).status_code == 403


def test_a_second_trigger_after_the_turn_is_a_no_op(client: TestClient) -> None:
    game_id, e, f = _table(client, auto=True)
    _order(client, game_id, e, "ENGLAND", ["F LON H"])
    _order(client, game_id, f, "FRANCE", ["A PAR H"])
    # The turn ran; nobody has ordered for F1901M yet, so a stray re-check must not run it again.
    assert api_shared.maybe_auto_process(game_id) == 0
    assert _phase(client, game_id) == "F1901M"


class TestSharedFinish:
    def test_a_deadline_that_fails_to_process_tells_nobody_it_did(self, client: TestClient, monkeypatch) -> None:
        """Before the shared finish, the scheduler notified "turn processed" even when
        process_turn had raised."""
        game_id, _e, _f = _table(client, auto=False)
        db_service.update_game_deadline(int(game_id), datetime.now(timezone.utc) - timedelta(minutes=1))

        def boom(_game_id: str) -> None:
            raise RuntimeError("adjudicator exploded")

        monkeypatch.setattr(game_service, "process_turn", boom)
        with OutboxProbe() as probe:
            api_shared.process_due_deadlines(datetime.now(timezone.utc))
        assert not probe.messages()
        assert db_service.get_game_by_game_id(game_id).deadline is None  # spent, not retried forever

    def test_every_trigger_reports_a_game_ending_turn_as_the_end(self, client: TestClient, monkeypatch) -> None:
        """The deadline path never passed ``game_ended``; now it comes from the board."""
        from tests.test_api_game_over import _drawn_game

        game_id, _tg = _drawn_game(client)
        seen: dict = {}
        monkeypatch.setattr(api_shared, "notify_turn_processed", lambda *a, **kw: seen.update(kw))
        api_shared.finish_processed_turn(game_id, int(game_id), prev_phase_code="S1901M", trigger="deadline")
        assert seen["game_ended"] is True and seen["trigger"] == "deadline"
