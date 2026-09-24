"""Orders sent one at a time must add up, not overwrite each other.

The bot submits one order per request (``/selectunit``, or several ``/order``
messages). ``submit_orders`` stored ``pending[power] = <this request's
orders>``, so each one wiped the last: a player ordered three German units in
the demo game and only the last, ``A MUN - RUH``, was ever adjudicated.
``merge=True`` (every bot path) now adds orders, a new order for a unit
replacing that unit's previous one. The web client still sends the full set
and replaces.
"""
import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api.shared import game_service
from tests.conftest import _get_db_url
from tests.test_auto_process import _table
from tests.test_quit_and_replace import _as, _register_and_login, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _germany(client: TestClient) -> tuple[str, str]:
    game_id = str(client.post("/games/create", json={"map_name": "standard"}, headers=_register_and_login(client, "mrg")).json()["game_id"])
    tg = _telegram_user(client, "germany")
    assert client.post(f"/games/{game_id}/join", json=_as(tg, power="GERMANY")).status_code == 200
    return game_id, tg


def _send(client: TestClient, game_id: str, tg: str, orders: list[str], merge: bool) -> None:
    resp = client.post("/games/set_orders", json=_as(tg, game_id=game_id, power="GERMANY", orders=orders, merge=merge))
    assert resp.status_code == 200, resp.text


def _pending(game_id: str) -> list[str]:
    return sorted(game_service.view(game_id)["orders"]["GERMANY"])


def test_one_at_a_time_adds_up(client: TestClient) -> None:
    game_id, tg = _germany(client)
    for order in ("A BER - KIE", "F KIE - DEN", "A MUN - RUH"):
        _send(client, game_id, tg, [order], merge=True)
    assert _pending(game_id) == ["A BER - KIE", "A MUN - RUH", "F KIE - DEN"]
    client.post(f"/games/{game_id}/process_turn", headers={"X-Bot-Secret": "test_bot_secret_for_tests"})
    moved = {u["location"] for u in game_service.view(game_id)["units_by_power"]["GERMANY"]}
    assert moved == {"KIE", "DEN", "RUH"}  # all three moved, not just the last


def test_a_new_order_for_a_unit_replaces_its_old_one(client: TestClient) -> None:
    game_id, tg = _germany(client)
    _send(client, game_id, tg, ["A BER - KIE", "A MUN H"], merge=True)
    _send(client, game_id, tg, ["A BER - SIL"], merge=True)
    assert _pending(game_id) == ["A BER - SIL", "A MUN H"]


def test_an_invalid_order_never_displaces_a_good_one(client: TestClient) -> None:
    game_id, tg = _germany(client)
    _send(client, game_id, tg, ["A BER - KIE"], merge=True)
    _send(client, game_id, tg, ["A BER - MOS"], merge=True)  # not adjacent
    assert _pending(game_id) == ["A BER - KIE"]


def test_without_merge_the_request_replaces_everything(client: TestClient) -> None:
    """The web client's contract: what it sends is the whole set."""
    game_id, tg = _germany(client)
    _send(client, game_id, tg, ["A BER - KIE", "A MUN H"], merge=False)
    _send(client, game_id, tg, ["F KIE - DEN"], merge=False)
    assert _pending(game_id) == ["F KIE - DEN"]


def test_auto_processing_waits_for_every_unit_not_the_first_order(client: TestClient) -> None:
    """W10 counted a power as done once it had *any* order; one-at-a-time bot
    entry would have run the turn after a player's first unit."""
    game_id, e, f = _table(client, auto=True)
    client.post("/games/set_orders", json=_as(e, game_id=game_id, power="ENGLAND", orders=["F LON H", "F EDI H", "A LVP H"], merge=True))
    first = client.post("/games/set_orders", json=_as(f, game_id=game_id, power="FRANCE", orders=["A PAR H"], merge=True)).json()
    assert first["auto_processed"] == 0
    status = client.get(f"/games/{game_id}/orders_status").json()
    assert status["incomplete"] == ["FRANCE"]
    client.post("/games/set_orders", json=_as(f, game_id=game_id, power="FRANCE", orders=["A MAR H"], merge=True))
    last = client.post("/games/set_orders", json=_as(f, game_id=game_id, power="FRANCE", orders=["F BRE H"], merge=True)).json()
    assert last["auto_processed"] == 1
