"""BA6: no turn is processed while a power has neither a player nor dummy status.

All three triggers are covered: the creator's manual ``POST /process_turn``,
auto-processing once every order is in, and the deadline scheduler. A game whose
missing powers are dummies (the bot's demo game included) is full and runs.
"""
import datetime

import pytest
from fastapi.testclient import TestClient

from server.api import app, process_due_deadlines
from server.api.shared import db_service, game_service
from tests.conftest import _get_db_url
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

BOT = {"X-Bot-Secret": BOT_SECRET}
OTHERS = ["AUSTRIA", "ENGLAND", "FRANCE", "ITALY", "RUSSIA", "TURKEY"]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _game(client: TestClient, dummies: list[str], seated: list[str], **create: object) -> tuple[str, str]:
    """A game created by a Telegram player who takes the first of ``seated``;
    fresh players take the rest. Returns ``(game_id, creator telegram_id)``."""
    creator = _telegram_user(client, "creator")
    resp = client.post(
        "/games/create", json=_as(creator, map_name="standard", dummy_powers=dummies, **create), headers=BOT
    )
    assert resp.status_code == 200, resp.text
    game_id = str(resp.json()["game_id"])
    for i, power in enumerate(seated):
        tg = creator if i == 0 else _telegram_user(client, power.lower())
        joined = client.post(f"/games/{game_id}/join", json=_as(tg, power=power))
        assert joined.status_code == 200 and joined.json()["status"] == "ok", joined.text
    return game_id, creator


def _phase(game_id: str) -> str:
    return game_service.view(game_id)["phase"]


def test_the_creator_cannot_process_a_game_with_empty_seats(client: TestClient) -> None:
    game_id, creator = _game(client, ["ITALY", "TURKEY"], ["GERMANY"])
    resp = client.post(f"/games/{game_id}/process_turn", json={"telegram_id": creator}, headers=BOT)
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == (
        "4 powers are unseated (Austria, England, France, Russia): seat players or mark them as dummies."
    )
    assert _phase(game_id) == "S1901M"


def test_one_empty_seat_is_named_in_the_singular(client: TestClient) -> None:
    game_id, _ = _game(client, ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA"], ["TURKEY"])
    resp = client.post(f"/games/{game_id}/process_turn", headers={"X-Admin-Token": "changeme"})
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "1 power is unseated (Austria): seat players or mark them as dummies."


def test_a_table_full_of_players_and_dummies_processes(client: TestClient) -> None:
    game_id, creator = _game(client, ["ITALY", "RUSSIA", "TURKEY"], ["GERMANY", "AUSTRIA", "ENGLAND", "FRANCE"])
    resp = client.post(f"/games/{game_id}/process_turn", json={"telegram_id": creator}, headers=BOT)
    assert resp.status_code == 200, resp.text
    assert _phase(game_id) == "F1901M"


def _orders(client: TestClient, tg: str, game_id: str, orders: list[str]) -> int:
    resp = client.post("/games/set_orders", json=_as(tg, game_id=game_id, power="GERMANY", orders=orders))
    assert resp.status_code == 200, resp.text
    assert all(r["success"] for r in resp.json()["results"]), resp.text
    return int(resp.json()["auto_processed"])


def test_auto_process_waits_for_a_full_table(client: TestClient) -> None:
    """A seat reopened mid-game (``dummy: false``) empties the table again.

    In a winter where only Germany has an adjustment to make, Germany's build
    is everything the phase waits for -- the reopened Austria has nothing to
    order -- so before BA6 auto-processing ran the phase anyway.
    """
    game_id, creator = _game(client, OTHERS, ["GERMANY"], auto_process=True)
    assert _orders(client, creator, game_id, ["A BER H", "A MUN H", "F KIE - DEN"]) == 1
    assert _orders(client, creator, game_id, ["A BER H", "A MUN H", "F DEN H"]) == 1
    assert _phase(game_id) == "W1901A"
    reopened = client.post(f"/games/{game_id}/dummies", json=_as(creator, power="AUSTRIA", dummy=False))
    assert reopened.status_code == 200, reopened.text
    assert _orders(client, creator, game_id, ["BUILD A KIE"]) == 0
    assert _phase(game_id) == "W1901A"
    # Leaving Austria to civil disorder again fills the table; the complete phase runs.
    redummied = client.post(f"/games/{game_id}/dummies", json=_as(creator, power="AUSTRIA", dummy=True))
    assert redummied.status_code == 200, redummied.text
    assert _phase(game_id) == "S1902M"


def test_the_scheduler_skips_a_game_with_empty_seats_and_spends_the_deadline(client: TestClient) -> None:
    game_id, _ = _game(client, ["ITALY", "TURKEY"], ["GERMANY"])
    numeric = int(db_service.get_game_by_game_id(game_id).id)
    now = datetime.datetime.now(datetime.timezone.utc)
    db_service.update_game_deadline(numeric, now - datetime.timedelta(minutes=1))
    process_due_deadlines(now)
    assert _phase(game_id) == "S1901M"
    # Spent, so the next tick does not find (and log) the same deadline again.
    assert db_service.get_game_by_game_id(game_id).deadline is None


def test_the_scheduler_processes_a_full_table(client: TestClient) -> None:
    game_id, _ = _game(client, ["AUSTRIA", "ENGLAND", "FRANCE", "ITALY", "RUSSIA"], ["GERMANY", "TURKEY"])
    numeric = int(db_service.get_game_by_game_id(game_id).id)
    now = datetime.datetime.now(datetime.timezone.utc)
    db_service.update_game_deadline(numeric, now - datetime.timedelta(minutes=1))
    process_due_deadlines(now)
    assert _phase(game_id) == "F1901M"


def test_the_demo_game_is_a_full_table_its_player_can_process(client: TestClient) -> None:
    """The bot's demo: Germany plus six dummies the server plays (admin.py)."""
    tg = _telegram_user(client, "demo")
    resp = client.post("/games/create", json=_as(tg, map_name="demo", dummy_powers=OTHERS, auto_process=True), headers=BOT)
    game_id = str(resp.json()["game_id"])
    assert client.post(f"/games/{game_id}/join", json=_as(tg, power="GERMANY")).status_code == 200
    resp = client.post(f"/games/{game_id}/process_turn", json={"telegram_id": tg}, headers=BOT)
    assert resp.status_code == 200, resp.text
    assert _phase(game_id) == "F1901M"
