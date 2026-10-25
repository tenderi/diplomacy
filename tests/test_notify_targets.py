"""BS2 and BS4: who a turn DM and the deadline reminder go to.

An eliminated or conceded power is owed no "orders are due" DM, and the table is told
once, when a turn eliminates a power. The 10-minute reminder goes only to the players
of powers still owing orders, names the phase, and says the minutes really left.
"""
from __future__ import annotations

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from engine.serialization import resolution_from_dict, state_to_dict
from engine.types import GameState, Location, PhaseType, Season, Unit, UnitKind
from server.api import app
from server.api import shared as api_shared
from tests.reliability_helpers import OutboxProbe
from tests.test_dm_addresses_you import _dms
from tests.test_draw_concede_notifications import GROUP, POWERS, _seeded_game

pytestmark = [pytest.mark.integration, pytest.mark.database]


def _fall_board(game_id: str) -> None:
    """Fall 1901: ITALY has no unit and one centre (ROM) that FRANCE's A TUS takes;
    TURKEY holds A ANK."""
    units = {
        Unit(UnitKind.ARMY, "FRANCE", Location("PAR")),
        Unit(UnitKind.ARMY, "FRANCE", Location("TUS")),
        Unit(UnitKind.ARMY, "ENGLAND", Location("LON")),
        Unit(UnitKind.ARMY, "GERMANY", Location("BER")),
        Unit(UnitKind.ARMY, "RUSSIA", Location("MOS")),
        Unit(UnitKind.ARMY, "TURKEY", Location("ANK")),
        Unit(UnitKind.ARMY, "AUSTRIA", Location("VIE")),
    }
    state = GameState(
        1901, Season.FALL, PhaseType.MOVEMENT,
        units=frozenset(units),
        ownership={
            "PAR": "FRANCE", "ROM": "ITALY", "LON": "ENGLAND", "BER": "GERMANY",
            "MOS": "RUSSIA", "ANK": "TURKEY", "VIE": "AUSTRIA",
        },
    )
    api_shared.game_service.restore_snapshot(game_id, state_to_dict(state), phase_code="F1901M")


def test_a_power_eliminated_by_the_turn_is_announced_once_and_a_conceded_one_gets_no_orders_dm() -> None:
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    by_power = {power: tg for power, (_h, tg) in zip(POWERS, users)}
    row_id = int(api_shared.db_service.get_game_by_game_id(game_id).id)
    api_shared.db_service.link_game_to_channel(game_id, GROUP, any_displacer=True)
    _fall_board(game_id)
    api_shared.game_service.concede(game_id, "TURKEY")
    api_shared.game_service.submit_orders(game_id, "FRANCE", ["A TUS - ROM"])
    api_shared.game_service.process_turn(game_id)
    assert api_shared.game_service.eliminated_in_turn(game_id, 0) == ["ITALY"]

    with OutboxProbe() as probe:
        api_shared.finish_processed_turn(game_id, row_id, prev_phase_code="F1901M", trigger="deadline")

    head = (
        f"The turn has been processed for game {game_id} because its deadline passed."
    )
    out = f"ITALY has been eliminated from game {game_id}: it has no units or supply centres left."
    dms = _dms(probe)
    assert dms[by_power["ITALY"]] == [
        f"{head}\nYour power ITALY has been eliminated from game {game_id}: it has no units or supply centres left."
    ]
    # TURKEY conceded earlier: no orders to give, but it still hears the table's news.
    assert dms[by_power["TURKEY"]] == [f"{head}\n{out}"]
    for power in ("ENGLAND", "FRANCE", "GERMANY", "RUSSIA", "AUSTRIA"):
        assert dms[by_power[power]] == [f"{head} Orders are due for Spring 1902 movement.\n{out}"]
    assert len(dms) == 7
    group = [r["message"] for r in probe.rows() if r["kind"] == "channel_text"]
    assert group == [
        f"🔔 Turn Processed - Game {game_id}\n"
        "The turn has been processed. Spring 1902 movement: new orders are due -- send them to me in private.\n"
        + out
    ]

    # A later turn does not announce it again, and still skips both powers that are out.
    with OutboxProbe() as later:
        api_shared.notify_turn_processed(
            game_id, row_id, trigger="manual", processed_turn=1, processed_phase="F1901M"
        )
    assert all("eliminated" not in m for m in later.messages())
    assert {str(r["telegram_id"]) for r in later.rows() if r["kind"] == "dm"} == {
        by_power[p] for p in POWERS if p not in ("TURKEY", "ITALY")
    }


def test_the_stored_eliminated_key_does_not_break_resolution_readers() -> None:
    client = TestClient(app)
    game_id, _users = _seeded_game(client)
    _fall_board(game_id)
    api_shared.game_service.submit_orders(game_id, "FRANCE", ["A TUS - ROM"])
    api_shared.game_service.process_turn(game_id)
    stored = api_shared.game_service.last_resolution(game_id)
    assert stored is not None and stored["eliminated"] == ["ITALY"]
    assert len(resolution_from_dict(stored).results) == len(stored["results"])
    response = client.get(f"/games/{game_id}/last_resolution")
    assert response.status_code == 200
    assert "eliminated" not in response.json()
    assert sorted(r["order_str"] for r in response.json()["results"] if r["power"] == "FRANCE") == ["A PAR H", "A TUS - ROM"]


def test_a_failed_elimination_read_still_sends_every_turn_dm(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    row_id = int(api_shared.db_service.get_game_by_game_id(game_id).id)
    api_shared.game_service.process_turn(game_id)

    def db_down(_game_id: str) -> frozenset[str]:
        raise OperationalError("SELECT 1", {}, Exception("db down"))

    monkeypatch.setattr(api_shared.game_service, "eliminated_powers", db_down)
    with OutboxProbe() as probe:
        api_shared.finish_processed_turn(game_id, row_id, prev_phase_code="S1901M", trigger="deadline")
    head = f"The turn has been processed for game {game_id} because its deadline passed."
    assert _dms(probe) == {tg: [f"{head} Orders are due for Fall 1901 movement."] for _h, tg in users}


def test_the_reminder_goes_to_powers_still_owing_orders_with_the_phase_and_minutes_left() -> None:
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    by_power = {power: tg for power, (_h, tg) in zip(POWERS, users)}
    row_id = int(api_shared.db_service.get_game_by_game_id(game_id).id)
    api_shared.db_service.link_game_to_channel(game_id, GROUP, any_displacer=True)
    api_shared.game_service.submit_orders(game_id, "ENGLAND", ["F LON H"])
    api_shared.game_service.submit_orders(game_id, "FRANCE", ["A PAR H"])
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    api_shared.db_service.update_game_deadline(row_id, now + datetime.timedelta(minutes=7, seconds=20))

    with OutboxProbe() as probe:
        api_shared.check_and_send_reminders(now)

    text = f"Reminder: orders for Spring 1901 movement in game {game_id} are due in 7 minutes."
    waiting = [p for p in POWERS if p not in ("ENGLAND", "FRANCE")]
    assert _dms(probe) == {by_power[p]: [text] for p in waiting}
    assert [r["message"] for r in probe.rows() if r["kind"] == "channel_text"] == [
        f"⏰ Game {game_id}: orders for Spring 1901 movement are due in 7 minutes"
        " (still to come: AUSTRIA, GERMANY, ITALY, RUSSIA, TURKEY). Orders go to me in private."
    ]


def test_the_reminder_never_says_zero_minutes_and_is_silent_when_nobody_owes_orders() -> None:
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    by_power = {power: tg for power, (_h, tg) in zip(POWERS, users)}
    row_id = int(api_shared.db_service.get_game_by_game_id(game_id).id)
    with OutboxProbe() as probe:
        api_shared._send_deadline_reminder(game_id, row_id, datetime.timedelta(seconds=20))
    assert _dms(probe) == {
        tg: [f"Reminder: orders for Spring 1901 movement in game {game_id} are due in 1 minute."]
        for tg in by_power.values()
    }
    orders = {
        "ENGLAND": "F LON H", "FRANCE": "A PAR H", "GERMANY": "A BER H", "ITALY": "A ROM H",
        "RUSSIA": "A MOS H", "TURKEY": "A CON H", "AUSTRIA": "A VIE H",
    }
    for power, order in orders.items():
        api_shared.game_service.submit_orders(game_id, power, [order])
    with OutboxProbe() as quiet:
        api_shared._send_deadline_reminder(game_id, row_id, datetime.timedelta(minutes=5))
    assert quiet.rows() == []
