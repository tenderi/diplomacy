"""CY: the bot-secret / admin-token guarded routes -- channels, waiting list, admin, archive.

CW covered the Bearer-auth routes. These routes admit the bot (``X-Bot-Secret``
header), an admin (``X-Admin-Token``) or, for a game's group, a seated player. For
each: nobody, a wrong secret and a plain web user are refused with the exact status
and message; the right credential gets through; a missing game is a 404, never a 500;
and a caller acting for someone else's power is refused.
"""
import itertools
import time
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from server.api import ADMIN_TOKEN, app
from server.api import shared as api_shared
from server.api.shared import BOT_SECRET, db_service
from tests.conftest import _get_db_url

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured"),
]

_counter = itertools.count()
NO_GAME = "99999999"
BOT = {"X-Bot-Secret": BOT_SECRET}
ADMIN = {"X-Admin-Token": ADMIN_TOKEN}
WRONG_BOT = {"X-Bot-Secret": "not-the-secret"}
WRONG_ADMIN = {"X-Admin-Token": "not-the-token"}
BOT_ONLY = "Not authenticated: this endpoint requires the 'X-Bot-Secret' header."
GROUP_PLAYERS_ONLY = "Only a player in this game can change its Telegram group"
LINK_FROM_GROUP = "A game is linked to a Telegram group from inside the group: add the bot and send /linkgroup there."
BAD_ADMIN = "Invalid admin token"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _user(client: TestClient) -> Dict[str, Any]:
    n = f"{int(time.time() * 1000000)}_{next(_counter)}"
    reg = client.post("/auth/register", json={"email": f"cy_{n}@example.com", "password": "testpass123"})
    assert reg.status_code == 200, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    uid = int(client.get("/auth/me", headers=headers).json()["id"])
    tg = str(time.time_ns() % 10**12)
    db_service.set_user_telegram_id(uid, tg)
    return {"h": headers, "tg": tg}


def _game(client: TestClient, a: Dict[str, Any], b: Dict[str, Any]) -> str:
    gid = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=a["h"]).json()["game_id"]
    for who, power in ((a, "FRANCE"), (b, "ENGLAND")):
        r = client.post(f"/games/{gid}/join", json={"power": power}, headers=who["h"])
        assert r.status_code == 200, r.text
    return gid


def _group() -> str:
    return f"-100{time.time_ns() % 10**12}"


@pytest.fixture(scope="module")
def table(client: TestClient) -> Dict[str, Any]:
    """A (FRANCE) and B (ENGLAND) play; C is outside. The game's group is linked."""
    a, b, c = (_user(client) for _ in range(3))
    gid = _game(client, a, b)
    group = _group()
    r = client.post(f"/games/{gid}/channel/link", json={"channel_id": group, "channel_name": "G"}, headers=BOT)
    assert r.status_code == 200, r.text
    return {"gid": gid, "group": group, "A": a, "B": b, "C": c}


def _expect(r: Any, status: int, detail: str) -> None:
    assert (r.status_code, r.json().get("detail")) == (status, detail), r.text


# ---------------------------------------------------------------- waiting list

@pytest.mark.parametrize("path", ["/waiting_list/join", "/waiting_list/leave"])
def test_waiting_list_needs_the_bot_secret(client: TestClient, table: Dict[str, Any], path: str) -> None:
    body = {"telegram_id": table["A"]["tg"]}
    _expect(client.post(path, json=body), 401, BOT_ONLY)
    _expect(client.post(path, json=body, headers=WRONG_BOT), 401, BOT_ONLY)
    _expect(client.post(path, json=body, headers=ADMIN), 401, BOT_ONLY)
    # A logged-in browser user is not the bot, even naming their own telegram id.
    _expect(client.post(path, json=body, headers=table["A"]["h"]), 401, BOT_ONLY)
    # The secret in the body is not a credential here.
    _expect(client.post(path, json={**body, "bot_secret": BOT_SECRET}), 401, BOT_ONLY)


def test_waiting_list_join_and_leave_with_the_secret(client: TestClient) -> None:
    api_shared.db_service.clear_waiting_list()
    try:
        body = {"telegram_id": _user(client)["tg"]}
        r = client.post("/waiting_list/join", json=body, headers=BOT)
        assert (r.status_code, r.json()["status"], r.json()["size"]) == (200, "queued", 1)
        r = client.post("/waiting_list/leave", json=body, headers=BOT)
        assert (r.status_code, r.json()["status"], r.json()["size"]) == (200, "removed", 0)
        r = client.post("/waiting_list/leave", json=body, headers=BOT)
        assert (r.status_code, r.json()["status"]) == (200, "not_queued")
    finally:
        api_shared.db_service.clear_waiting_list()


def test_waiting_list_join_unknown_telegram_id_is_404(client: TestClient) -> None:
    r = client.post("/waiting_list/join", json={"telegram_id": "424242424242"}, headers=BOT)
    _expect(r, 404, "No registered user for this telegram_id -- register before joining the waiting list")


def test_waiting_list_status_is_public_and_hides_ids(client: TestClient) -> None:
    r = client.get("/waiting_list")
    assert (r.status_code, set(r.json())) == (200, {"size", "required", "slots_remaining"})


# ----------------------------------------------------------------- channel read

def test_channel_game_lookup_is_bot_only(client: TestClient, table: Dict[str, Any]) -> None:
    path = f"/channels/{table['group']}/game"
    _expect(client.get(path), 401, BOT_ONLY)
    _expect(client.get(path, headers=WRONG_BOT), 401, BOT_ONLY)
    _expect(client.get(path, headers=table["A"]["h"]), 401, BOT_ONLY)
    _expect(client.get(path, headers=ADMIN), 401, BOT_ONLY)
    r = client.get(path, headers=BOT)
    assert (r.status_code, r.json()["linked"], r.json()["game_id"]) == (200, True, table["gid"])
    r = client.get("/channels/-1000000000000000/game", headers=BOT)
    assert (r.status_code, r.json()) == (200, {"linked": False})


def test_channel_info_visible_to_players_bot_and_admin_only(client: TestClient, table: Dict[str, Any]) -> None:
    path = f"/games/{table['gid']}/channel"
    for headers in ({}, WRONG_BOT, WRONG_ADMIN, table["C"]["h"]):
        _expect(client.get(path, headers=headers), 403, GROUP_PLAYERS_ONLY)
    for headers in (BOT, ADMIN, table["A"]["h"], table["B"]["h"]):
        r = client.get(path, headers=headers)
        assert (r.status_code, r.json()["linked"], r.json()["channel_id"]) == (200, True, table["group"])


def test_channel_info_of_a_missing_game(client: TestClient, table: Dict[str, Any]) -> None:
    path = f"/games/{NO_GAME}/channel"
    _expect(client.get(path, headers=table["A"]["h"]), 403, GROUP_PLAYERS_ONLY)
    r = client.get(path, headers=BOT)
    assert (r.status_code, r.json()["linked"]) == (200, False)


# --------------------------------------------------------------- channel writes

# (method, path, body) -- every write that needs a player, the bot or an admin.
GROUP_WRITES = [
    ("PUT", "/games/{gid}/channel/settings", {"auto_post_maps": True}),
    ("POST", "/games/{gid}/channel/settings", {"auto_post_maps": True}),
    ("POST", "/games/{gid}/channel/map", None),
    ("POST", "/games/{gid}/channel/broadcast", {"telegram_id": "{tg}", "message": "hello"}),
    ("POST", "/games/{gid}/channel/thread", {"topic": "t"}),
    ("GET", "/games/{gid}/channel/timeline", None),
    ("POST", "/games/{gid}/channel/timeline", None),
    ("POST", "/games/{gid}/channel/dashboard", None),
    ("DELETE", "/games/{gid}/channel/unlink", None),
]
NOT_DELETE = [g for g in GROUP_WRITES if g[0] != "DELETE"]
# Needing a linked group: a game without one is a 404 naming that.
NEEDS_GROUP = [g for g in NOT_DELETE if g[1].rsplit("/", 1)[1] in ("broadcast", "thread", "dashboard") or g[0] == "POST" and g[1].endswith("timeline")]


def _call(client: TestClient, table: Dict[str, Any], method: str, path: str, body: Any, headers: Dict[str, str], gid: str = "") -> Any:
    if body:
        body = {k: (v.format(tg=table["A"]["tg"]) if isinstance(v, str) else v) for k, v in body.items()}
    return client.request(method, path.format(gid=gid or table["gid"]), json=body, headers=headers)


@pytest.mark.parametrize("method,path,body", GROUP_WRITES)
def test_group_writes_refuse_everyone_else(client: TestClient, table: Dict[str, Any], method: str, path: str, body: Any) -> None:
    for headers in ({}, WRONG_BOT, WRONG_ADMIN, table["C"]["h"]):
        _expect(_call(client, table, method, path, body, headers), 403, GROUP_PLAYERS_ONLY)


@pytest.mark.parametrize("method,path,body", NOT_DELETE)
def test_group_writes_succeed_for_bot_admin_and_players(client: TestClient, table: Dict[str, Any], method: str, path: str, body: Any) -> None:
    for headers in (BOT, ADMIN, table["A"]["h"], table["B"]["h"]):
        r = _call(client, table, method, path, body, headers)
        assert r.status_code == 200, (headers, r.text)


@pytest.mark.parametrize("method,path,body", NEEDS_GROUP)
def test_group_posts_on_a_game_without_a_group_are_404(client: TestClient, table: Dict[str, Any], method: str, path: str, body: Any) -> None:
    _expect(_call(client, table, method, path, body, BOT, gid=NO_GAME), 404, f"Game {NO_GAME} is not linked to a channel")


def test_missing_game_map_unlink_and_timeline(client: TestClient) -> None:
    _expect(client.post(f"/games/{NO_GAME}/channel/map", headers=BOT), 404, f"Game {NO_GAME} not found")
    _expect(client.delete(f"/games/{NO_GAME}/channel/unlink", headers=BOT), 404, f"Game {NO_GAME} not found")
    _expect(client.get(f"/games/{NO_GAME}/channel/timeline", headers=BOT), 404, f"Game {NO_GAME} not found")


def test_unlinked_game_map_is_404(client: TestClient) -> None:
    gid = _game(client, _user(client), _user(client))
    _expect(client.post(f"/games/{gid}/channel/map", headers=BOT), 404, f"Game {gid} is not linked to a channel")


def test_settings_of_a_missing_game_are_404_not_500(client: TestClient) -> None:
    # Used to raise ValueError out of the DAL: a 500.
    for method in (client.put, client.post):
        r = method(f"/games/{NO_GAME}/channel/settings", json={"auto_post_maps": True}, headers=BOT)
        _expect(r, 404, f"Game {NO_GAME} not found")


def test_unlink_by_the_bot_and_by_a_player(client: TestClient) -> None:
    a, b = _user(client), _user(client)
    for headers in (BOT, a["h"]):
        gid = _game(client, a, b)
        assert client.post(f"/games/{gid}/channel/link", json={"channel_id": _group()}, headers=BOT).status_code == 200
        r = client.delete(f"/games/{gid}/channel/unlink", headers=headers)
        assert (r.status_code, r.json()["game_id"]) == (200, gid)
        assert client.get(f"/games/{gid}/channel", headers=BOT).json()["linked"] is False


# ------------------------------------------------------------------- broadcast

def test_broadcast_cannot_speak_for_another_power(client: TestClient, table: Dict[str, Any]) -> None:
    path = f"/games/{table['gid']}/channel/broadcast"
    # The bot names a power, but only the one the Telegram user holds.
    r = client.post(path, json={"telegram_id": table["A"]["tg"], "message": "hi", "power": "ENGLAND"}, headers=BOT)
    _expect(r, 403, f"You do not hold ENGLAND in game {table['gid']}")
    # So does a seated web user, whatever the body says.
    r = client.post(path, json={"telegram_id": table["B"]["tg"], "message": "hi", "power": "FRANCE"}, headers=table["B"]["h"])
    _expect(r, 403, f"You do not hold FRANCE in game {table['gid']}")
    # A telegram id with no seat holds no power.
    r = client.post(path, json={"telegram_id": table["C"]["tg"], "message": "hi", "power": "FRANCE"}, headers=BOT)
    _expect(r, 403, f"You do not hold FRANCE in game {table['gid']}")
    r = client.post(path, json={"telegram_id": table["A"]["tg"], "message": "hi", "power": "FRANCE"}, headers=BOT)
    assert (r.status_code, r.json()["status"]) == (200, "queued")


# ------------------------------------------------------------------------ link

def test_link_is_bot_or_admin_only(client: TestClient, table: Dict[str, Any]) -> None:
    path = f"/games/{table['gid']}/channel/link"
    body = {"channel_id": table["group"]}
    for headers in ({}, WRONG_BOT, WRONG_ADMIN, table["A"]["h"]):
        _expect(client.post(path, json=body, headers=headers), 403, LINK_FROM_GROUP)
    for headers in (BOT, ADMIN):
        r = client.post(path, json=body, headers=headers)
        assert (r.status_code, r.json()["game_id"]) == (200, table["gid"]), r.text


def test_link_of_a_missing_game_is_404(client: TestClient) -> None:
    for headers in (BOT, ADMIN):
        r = client.post(f"/games/{NO_GAME}/channel/link", json={"channel_id": "-1001"}, headers=headers)
        _expect(r, 404, f"Game {NO_GAME} not found")


def test_only_a_player_of_the_losing_game_may_move_a_link(client: TestClient, table: Dict[str, Any]) -> None:
    c, b = _user(client), _user(client)
    other = _game(client, c, b)
    path = f"/games/{other}/channel/link"
    taken = f"That Telegram group already belongs to game {table['gid']}. Only a player of game {table['gid']} can move the group to another game."
    body = {"channel_id": table["group"]}
    _expect(client.post(path, json=body, headers=BOT), 409, taken)
    _expect(client.post(path, json={**body, "telegram_id": c["tg"]}, headers=BOT), 409, taken)
    _expect(client.post(path, json={**body, "telegram_id": "5550001"}, headers=BOT), 409, taken)
    # A player of the game that holds it may move it; admin moves it back.
    r = client.post(path, json={**body, "telegram_id": table["A"]["tg"]}, headers=BOT)
    assert (r.status_code, r.json()["replaced_game_id"]) == (200, table["gid"]), r.text
    r = client.post(f"/games/{table['gid']}/channel/link", json=body, headers=ADMIN)
    assert (r.status_code, r.json()["replaced_game_id"]) == (200, other), r.text


# ----------------------------------------------------------------------- admin

ADMIN_ROUTES = [
    ("DELETE", "/admin/games/1"),
    ("POST", "/admin/delete_all_games"),
    ("GET", "/admin/games_count"),
    ("GET", "/admin/users_count"),
    ("POST", "/admin/cleanup_old_maps"),
    ("GET", "/admin/map_cache_stats"),
    ("POST", "/admin/clear_map_cache"),
    ("POST", "/admin/preload_maps"),
    ("GET", "/admin/connection_pool_status"),
    ("POST", "/admin/connection_pool_reset"),
    ("GET", "/admin/response_cache_stats"),
    ("POST", "/admin/clear_response_cache"),
    ("POST", "/admin/invalidate_cache/1"),
    ("GET", f"/games/{NO_GAME}/export"),
    ("POST", "/games/import"),
]


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_routes_refuse_everyone_but_the_admin(client: TestClient, table: Dict[str, Any], method: str, path: str) -> None:
    body = {"game": {}} if path == "/games/import" else None
    # No X-Admin-Token header: it is required (422), and neither the bot secret
    # nor a web login stands in for it.
    for headers in ({}, BOT, table["A"]["h"]):
        r = client.request(method, path, json=body, headers=headers)
        assert (r.status_code, r.json()["detail"][0]["loc"]) == (422, ["header", "x-admin-token"]), r.text
    # A wrong token, including the bot secret offered as one: 403.
    for headers in (WRONG_ADMIN, {"X-Admin-Token": BOT_SECRET}, {"X-Admin-Token": ""}):
        r = client.request(method, path, json=body, headers=headers)
        assert (r.status_code, r.json()["detail"]) == (403, BAD_ADMIN), r.text


def test_admin_reads_succeed_with_the_token(client: TestClient) -> None:
    for path in ("/admin/games_count", "/admin/users_count"):
        r = client.get(path, headers=ADMIN)
        assert (r.status_code, isinstance(r.json()["count"], int)) == (200, True), r.text
    for path in ("/admin/map_cache_stats", "/admin/response_cache_stats", "/admin/connection_pool_status"):
        assert client.get(path, headers=ADMIN).status_code == 200


def test_admin_delete_of_a_missing_game(client: TestClient) -> None:
    _expect(client.delete(f"/admin/games/{NO_GAME}", headers=ADMIN), 404, "Game not found")


# --------------------------------------------------------------------- archive

def test_export_of_a_missing_game_is_404(client: TestClient) -> None:
    _expect(client.get(f"/games/{NO_GAME}/export", headers=ADMIN), 404, "Game not found")


def test_export_needs_the_admin_even_for_a_player(client: TestClient, table: Dict[str, Any]) -> None:
    path = f"/games/{table['gid']}/export"
    assert client.get(path, headers=table["A"]["h"]).status_code == 422
    r = client.get(path, headers=ADMIN)
    assert (r.status_code, r.json()["game"]["game_id"]) == (200, table["gid"])
