"""Cached reads must never show a player the world before their own write.

``GET /games/{id}/state`` (30 s), ``GET /games/{id}/players`` (60 s) and
``GET /users/{telegram_id}/games`` (60 s) are answered from ``response_cache``. Each
test warms the cache, makes a write through the API, and reads again: the read must
show the write, not a copy from before it.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from persistence.database import GameModel
from server.api import ADMIN_TOKEN, app
from server.api.shared import db_service
from server.response_cache import clear_response_cache
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

BOT = {"X-Bot-Secret": BOT_SECRET}


@pytest.fixture
def client() -> TestClient:
    clear_response_cache()
    return TestClient(app)


def _game(client: TestClient) -> tuple[str, str]:
    tg = _telegram_user(client, "cachey")
    game_id = str(client.post("/games/create", json=_as(tg, map_name="standard"), headers=BOT).json()["game_id"])
    return game_id, tg


def _state(client: TestClient, game_id: str) -> dict:
    return client.get(f"/games/{game_id}/state").json()


def _my_games(client: TestClient, tg: str) -> list[str]:
    return [str(g["game_id"]) for g in client.get(f"/users/{tg}/games", headers=BOT).json()["games"]]


def _seats(client: TestClient, game_id: str) -> dict[str, object]:
    """power -> the Telegram id of whoever holds it (the route sends only ``user_id``)."""
    seats = {}
    for p in client.get(f"/games/{game_id}/players").json():
        user = db_service.get_user_by_id(p["user_id"]) if p["user_id"] is not None else None
        seats[p["power"]] = user.telegram_id if user is not None else None
    return seats


def test_joining_shows_in_my_games_and_the_seat_list(client: TestClient) -> None:
    game_id, tg = _game(client)
    assert game_id not in _my_games(client, tg) and _seats(client, game_id) == {}  # warm both
    assert client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE")).status_code == 200
    assert game_id in _my_games(client, tg)
    assert _seats(client, game_id) == {"FRANCE": tg}


def test_pending_orders_stay_out_of_the_public_state(client: TestClient) -> None:
    """Pending orders are secret until the turn is processed: the cached public
    ``/state`` never carries them, and the owner reads them from
    ``/orders/{power}`` (uncached), which follows every write."""
    game_id, tg = _game(client)
    client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
    fill_with_dummies(game_id)
    own, bot = {"telegram_id": tg}, {"X-Bot-Secret": BOT_SECRET}
    assert "orders" not in _state(client, game_id)  # warm
    assert client.post("/games/set_orders", json=_as(tg, game_id=game_id, power="FRANCE", orders=["A PAR - BUR"])).status_code == 200
    assert "orders" not in _state(client, game_id)
    assert client.get(f"/games/{game_id}/orders/FRANCE", params=own, headers=bot).json()["orders"] == ["A PAR - BUR"]
    assert client.post(f"/games/{game_id}/orders/FRANCE/clear", json=_as(tg)).status_code == 200
    assert client.get(f"/games/{game_id}/orders/FRANCE", params=own, headers=bot).json()["orders"] == []


def test_a_processed_turn_shows_the_new_phase(client: TestClient) -> None:
    game_id, _tg = _game(client)
    fill_with_dummies(game_id)
    assert _state(client, game_id)["phase"] == "S1901M"  # warm
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    assert _state(client, game_id)["phase"] == "F1901M"


def test_an_admin_restore_shows_the_restored_phase(client: TestClient) -> None:
    game_id, _tg = _game(client)
    fill_with_dummies(game_id)
    snaps = client.get(f"/games/{game_id}/snapshots").json()["snapshots"]
    (opening,) = [s["id"] for s in snaps if s["turn"] == 0]
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    assert _state(client, game_id)["phase"] == "F1901M"  # warm
    restored = client.post(f"/games/{game_id}/restore/{opening}", headers={"X-Admin-Token": ADMIN_TOKEN})
    assert restored.status_code == 200, restored.text
    assert _state(client, game_id)["phase"] == "S1901M"


def test_quitting_leaves_my_games_and_frees_the_seat(client: TestClient) -> None:
    game_id, tg = _game(client)
    client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
    assert game_id in _my_games(client, tg) and _seats(client, game_id) == {"FRANCE": tg}  # warm
    assert client.post(f"/games/{game_id}/quit", json=_as(tg)).status_code == 200
    assert game_id not in _my_games(client, tg)
    assert _seats(client, game_id) == {"FRANCE": None}


def test_taking_over_a_seat_shows_for_the_newcomer(client: TestClient) -> None:
    game_id, quitter = _game(client)
    client.post(f"/games/{game_id}/join", json=_as(quitter, power="FRANCE"))
    client.post(f"/games/{game_id}/quit", json=_as(quitter))
    newcomer = _telegram_user(client, "newcomer")
    assert _my_games(client, newcomer) == [] and _seats(client, game_id) == {"FRANCE": None}  # warm
    assert client.post(f"/games/{game_id}/replace", json=_as(newcomer, power="FRANCE")).status_code == 200
    assert _my_games(client, newcomer) == [game_id]
    assert _seats(client, game_id) == {"FRANCE": newcomer}


def test_a_draw_vote_and_a_dummy_show_in_the_state(client: TestClient) -> None:
    game_id, tg = _game(client)
    client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
    assert _state(client, game_id)["dummy_powers"] == []  # warm
    assert client.post(f"/games/{game_id}/dummies", json=_as(tg, power="ITALY", dummy=True)).status_code == 200
    assert _state(client, game_id)["dummy_powers"] == ["ITALY"]


def _web_player(client: TestClient) -> tuple[dict[str, str], str]:
    """A web account holding FRANCE in a fresh game. Returns ``(auth headers, game_id)``."""
    email = f"cc2_{uuid.uuid4().hex}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert reg.status_code == 200, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    game_id, _ = _game(client)
    assert client.post(f"/games/{game_id}/join", json={"power": "FRANCE"}, headers=headers).status_code == 200
    return headers, game_id


def _nicknames(client: TestClient, game_id: str) -> list[object]:
    return [p["nickname"] for p in client.get(f"/games/{game_id}/players").json()]


def _link(client: TestClient, headers: dict[str, str], tg: str) -> None:
    code = client.post("/auth/me/link_code", headers=headers).json()["code"]
    assert client.post("/auth/telegram/link", json={"telegram_id": tg, "code": code}).status_code == 200


def test_a_web_nickname_shows_in_the_cached_seat_list(client: TestClient) -> None:
    headers, game_id = _web_player(client)
    assert _nicknames(client, game_id) == [None]  # warm
    nick = f"Nick{uuid.uuid4().hex[:8]}"
    assert client.patch("/auth/me", json={"nickname": nick}, headers=headers).status_code == 200
    assert _nicknames(client, game_id) == [nick]


def test_a_bot_nickname_shows_in_the_cached_seat_list(client: TestClient) -> None:
    game_id, tg = _game(client)
    client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
    assert _nicknames(client, game_id) == [None]  # warm
    nick = f"Bot{uuid.uuid4().hex[:8]}"
    r = client.post("/users/nickname", json={"telegram_id": tg, "bot_secret": BOT_SECRET, "nickname": nick})
    assert r.status_code == 200, r.text
    assert _nicknames(client, game_id) == [nick]


def test_unlinking_telegram_drops_the_cached_game_list(client: TestClient) -> None:
    headers, game_id = _web_player(client)
    tg = str(int(_telegram_user(client, "unlinkee")) + 7)  # an id no account holds yet
    _link(client, headers, tg)
    assert _my_games(client, tg) == [game_id]  # warm
    assert client.post("/auth/me/unlink_telegram", headers=headers).status_code == 200
    assert client.get(f"/users/{tg}/games", headers=BOT).status_code == 404


def test_relinking_telegram_drops_the_old_ids_cached_game_list(client: TestClient) -> None:
    headers, game_id = _web_player(client)
    old = str(int(_telegram_user(client, "relink")) + 11)
    new = str(int(old) + 13)
    _link(client, headers, old)
    assert _my_games(client, old) == [game_id]  # warm
    _link(client, headers, new)
    assert client.get(f"/users/{old}/games", headers=BOT).status_code == 404
    assert _my_games(client, new) == [game_id]


def _my_game_rows(client: TestClient, tg: str) -> dict[str, dict]:
    return {str(g["game_id"]): g for g in client.get(f"/users/{tg}/games", headers=BOT).json()["games"]}


def test_a_processed_turn_shows_the_new_turn_in_my_games(client: TestClient) -> None:
    game_id, tg = _game(client)
    client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
    fill_with_dummies(game_id)
    turn = _my_game_rows(client, tg)[game_id]["current_turn"]  # warm
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    assert _my_game_rows(client, tg)[game_id]["current_turn"] == turn + 1


def test_an_admin_restore_shows_the_restored_status_in_my_games(client: TestClient) -> None:
    game_id, tg = _game(client)
    client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
    fill_with_dummies(game_id)
    (opening,) = [s["id"] for s in client.get(f"/games/{game_id}/snapshots").json()["snapshots"] if s["turn"] == 0]
    with db_service.session_factory() as session:  # the game ended after the snapshot
        session.query(GameModel).filter(GameModel.game_id == game_id).update({"status": "completed"})
        session.commit()
    assert _my_game_rows(client, tg)[game_id]["status"] == "completed"  # warm
    restored = client.post(f"/games/{game_id}/restore/{opening}", headers={"X-Admin-Token": ADMIN_TOKEN})
    assert restored.status_code == 200, restored.text
    assert _my_game_rows(client, tg)[game_id]["status"] == "active"


def test_marking_a_player_inactive_drops_the_game_from_their_list(client: TestClient) -> None:
    game_id, tg = _game(client)
    client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
    assert game_id in _my_games(client, tg)  # warm
    resp = client.post(f"/games/{game_id}/players/FRANCE/mark_inactive", json={"admin_token": ADMIN_TOKEN})
    assert resp.status_code == 200, resp.text
    assert game_id not in _my_games(client, tg)


def test_importing_a_game_shows_it_in_a_players_list(client: TestClient) -> None:
    game_id, tg = _game(client)
    client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
    doc = client.get(f"/games/{game_id}/export", headers={"X-Admin-Token": ADMIN_TOKEN}).json()
    assert _my_games(client, tg) == [game_id]  # warm
    imported = client.post("/games/import", json=doc, headers={"X-Admin-Token": ADMIN_TOKEN})
    assert imported.status_code == 200, imported.text
    assert sorted(_my_games(client, tg)) == sorted([game_id, str(imported.json()["game_id"])])


def test_an_admin_added_seat_shows_in_the_seat_list(client: TestClient) -> None:
    game_id, _tg = _game(client)
    assert _seats(client, game_id) == {}  # warm
    resp = client.post("/games/add_player", json={"game_id": game_id, "power": "FRANCE"}, headers={"X-Admin-Token": ADMIN_TOKEN})
    assert resp.status_code == 200, resp.text
    assert _seats(client, game_id) == {"FRANCE": None}


def test_deleting_every_game_empties_the_cached_state_and_lists(client: TestClient) -> None:
    game_id, tg = _game(client)
    client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
    assert _state(client, game_id)["phase"] == "S1901M" and game_id in _my_games(client, tg)  # warm
    assert client.post("/admin/delete_all_games", headers={"X-Admin-Token": ADMIN_TOKEN}).status_code == 200
    assert client.get(f"/games/{game_id}/state").status_code == 404
    assert game_id not in _my_games(client, tg)
