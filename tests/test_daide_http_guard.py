"""DD2: the HTTP API never seats a player in, or acts as a power in, the DAIDE
listener's game. Its seats are live DAIDE connections held in memory; an HTTP
join used to take FRANCE while a DAIDE client held it, and HTTP orders then
overwrote the client's. Every such write is refused with 409; reads and an
admin's turn processing stay allowed, and a normal game is unaffected.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server._api_module import app
from server.api.shared import DAIDE_GAME_REFUSAL, db_service, game_service
from tests.bot_client import BotTestClient
from tests.conftest import _get_db_url
from tests.test_anonymous_games import _BOT, _as, _telegram_user

pytestmark = [
    pytest.mark.integration,
    pytest.mark.database,
    pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured"),
]

ADMIN = {"X-Admin-Token": "changeme"}


@pytest.fixture
def client() -> BotTestClient:
    return BotTestClient(app)


def _daide_game() -> str:
    return game_service.create_game(map_name="standard", daide=True)


def _seat(game_id: str, tg: str, power: str) -> None:
    """A seat row in the DAIDE game, as an older server's HTTP join left one:
    the order, vote and flag writes must refuse even when it exists."""
    numeric = int(db_service.get_game_by_game_id(game_id).id)
    user = db_service.get_user_by_telegram_id(tg)
    db_service.create_player(numeric, power, int(user.id))


def _assert_refused(r) -> None:
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == DAIDE_GAME_REFUSAL
    assert r.headers["X-Error-Code"] == "daide_game"


def test_join_with_a_power_is_refused(client: TestClient) -> None:
    game_id = _daide_game()
    tg, _ = _telegram_user(client, "Djn")
    _assert_refused(client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE")))
    assert db_service.get_players_by_game_id(int(db_service.get_game_by_game_id(game_id).id)) == []


def test_join_without_a_power_is_refused(client: TestClient) -> None:
    game_id = _daide_game()
    tg, _ = _telegram_user(client, "Djr")
    _assert_refused(client.post(f"/games/{game_id}/join", json=_as(tg)))


def test_replace_is_refused(client: TestClient) -> None:
    game_id = _daide_game()
    holder, _ = _telegram_user(client, "Dho")
    _seat(game_id, holder, "FRANCE")
    numeric = int(db_service.get_game_by_game_id(game_id).id)
    player = db_service.get_player_by_game_id_and_power(game_id=numeric, power="FRANCE")
    db_service.assign_player_seat(int(player.id), None, False)  # vacated
    tg, _ = _telegram_user(client, "Drp")
    _assert_refused(client.post(f"/games/{game_id}/replace", json=_as(tg, power="FRANCE")))


def test_making_a_power_a_dummy_is_refused_even_for_an_admin(client: TestClient) -> None:
    game_id = _daide_game()
    _assert_refused(client.post(f"/games/{game_id}/dummies", json={"power": "FRANCE", "dummy": True}, headers=ADMIN))
    assert game_service.dummy_powers(game_id) == frozenset()


def test_admin_add_player_is_refused(client: TestClient) -> None:
    game_id = _daide_game()
    _assert_refused(client.post("/games/add_player", json={"game_id": game_id, "power": "FRANCE"}, headers=ADMIN))


def test_orders_are_refused_replace_and_merge(client: TestClient) -> None:
    game_id = _daide_game()
    tg, _ = _telegram_user(client, "Dor")
    _seat(game_id, tg, "FRANCE")
    for merge in (False, True):
        body = {"game_id": game_id, "power": "FRANCE", "orders": ["A PAR - BUR"], "merge": merge, **_as(tg)}
        _assert_refused(client.post("/games/set_orders", json=body))
    assert (game_service.pending_orders_view(game_id) or {}).get("FRANCE", []) == []


def test_clearing_orders_is_refused(client: TestClient) -> None:
    game_id = _daide_game()
    tg, _ = _telegram_user(client, "Dcl")
    _seat(game_id, tg, "FRANCE")
    _assert_refused(client.post(f"/games/{game_id}/orders/FRANCE/clear", json=_as(tg)))


def test_draw_vote_is_refused(client: TestClient) -> None:
    game_id = _daide_game()
    tg, _ = _telegram_user(client, "Ddv")
    _seat(game_id, tg, "FRANCE")
    _assert_refused(client.post(f"/games/{game_id}/draw_vote", json=_as(tg, power="FRANCE", vote=True)))


def test_wait_flag_is_refused(client: TestClient) -> None:
    game_id = _daide_game()
    tg, _ = _telegram_user(client, "Dwf")
    _seat(game_id, tg, "FRANCE")
    _assert_refused(client.post(f"/games/{game_id}/wait", json=_as(tg, power="FRANCE", waiting=True)))


def test_concede_is_refused(client: TestClient) -> None:
    game_id = _daide_game()
    tg, _ = _telegram_user(client, "Dcn")
    _seat(game_id, tg, "FRANCE")
    _assert_refused(client.post(f"/games/{game_id}/concede", json=_as(tg, power="FRANCE")))


def test_deadline_proposal_is_refused(client: TestClient) -> None:
    game_id = _daide_game()
    tg, _ = _telegram_user(client, "Ddp")
    _seat(game_id, tg, "FRANCE")
    _assert_refused(client.post(f"/games/{game_id}/deadline/propose", json=_as(tg, power="FRANCE", hours=24)))


@pytest.mark.parametrize("path, extra", [("vote", {"vote": True}), ("withdraw", {})])
def test_deadline_vote_and_withdraw_are_refused(client: TestClient, path: str, extra: dict) -> None:
    game_id = _daide_game()
    tg, _ = _telegram_user(client, "Ddw")
    _seat(game_id, tg, "FRANCE")
    _assert_refused(client.post(f"/games/{game_id}/deadline/{path}", json=_as(tg, power="FRANCE", **extra)))


def test_reads_and_admin_processing_stay_allowed(client: TestClient) -> None:
    game_id = _daide_game()
    assert client.get(f"/games/{game_id}/state").status_code == 200
    r = client.post(f"/games/{game_id}/process_turn", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert game_service.meta(game_id)["phase_code"] == "F1901M"


def test_the_daide_game_is_not_listed_for_joining(client: TestClient) -> None:
    daide_id = _daide_game()
    tg, _ = _telegram_user(client, "Dls")
    r = client.post("/games/create", json={"map_name": "standard", **_as(tg)}, headers=_BOT)
    normal_id = str(r.json()["game_id"])
    for headers in ({}, _BOT):
        listed = {str(g["game_id"]) for g in client.get("/games", headers=headers).json()["games"]}
        assert normal_id in listed
        assert daide_id not in listed


def test_a_normal_game_still_seats_its_joiners(client: TestClient) -> None:
    tg, _ = _telegram_user(client, "Dnm")
    r = client.post("/games/create", json={"map_name": "standard", **_as(tg)}, headers=_BOT)
    game_id = str(r.json()["game_id"])
    r = client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
    assert r.status_code == 200, r.text
    assert r.json()["power"] == "FRANCE"
