"""CW: per-power authorization, 404 and 409 paths of the game routes, via JWT.

A player acting for a power they do not hold, a non-member acting at all, and a
game that does not exist must each come out as the exact 403/404 -- never a 500
and never a success. Messages must keep private mail private. Everything here
authenticates with a Bearer token, so it does not depend on how the bot secret
is passed.
"""
import itertools
import time
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from server.api import app
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured"),
]

_counter = itertools.count()
NO_GAME = "99999999"
NOT_AUTHORIZED = "You are not authorized to act for this power."
NOT_PLAYER = "You are not a player in this game."


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _user(client: TestClient) -> Dict[str, str]:
    email = f"cw_{int(time.time() * 1000)}_{next(_counter)}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert reg.status_code == 200, reg.text
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


@pytest.fixture(scope="module")
def table(client: TestClient) -> Dict[str, Any]:
    """A running game: A (creator) plays FRANCE, B ENGLAND, D GERMANY; C is outside."""
    a, b, c, d = (_user(client) for _ in range(4))
    gid = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=a).json()["game_id"]
    for headers, power in ((a, "FRANCE"), (b, "ENGLAND"), (d, "GERMANY")):
        r = client.post(f"/games/{gid}/join", json={"power": power}, headers=headers)
        assert r.status_code == 200, r.text
    fill_with_dummies(gid)
    return {"gid": gid, "A": a, "B": b, "C": c, "D": d}


def _check(client: TestClient, table: Dict[str, Any], method: str, path: str, body: Any, who: str, status: int, detail: str) -> None:
    url = path.format(gid=table["gid"])
    r = client.request(method, url, json=body, headers=table[who] if who in table else {})
    assert (r.status_code, r.json().get("detail")) == (status, detail), r.text


# (method, path, body, caller, expected status, expected detail)
POWER_BOUND = [
    # A power that is not the caller's: 403, whoever the caller is.
    ("POST", "/games/{gid}/wait", {"power": "FRANCE"}, "B", 403, NOT_AUTHORIZED),
    ("POST", "/games/{gid}/wait", {"power": "FRANCE"}, "C", 403, NOT_AUTHORIZED),
    ("POST", "/games/{gid}/draw_vote", {"power": "FRANCE", "vote": True}, "B", 403, NOT_AUTHORIZED),
    ("POST", "/games/{gid}/draw_vote", {"power": "FRANCE", "vote": True}, "C", 403, NOT_AUTHORIZED),
    ("POST", "/games/{gid}/concede", {"power": "FRANCE"}, "B", 403, NOT_AUTHORIZED),
    ("POST", "/games/{gid}/concede", {"power": "FRANCE"}, "C", 403, NOT_AUTHORIZED),
    ("POST", "/games/{gid}/deadline/propose", {"power": "FRANCE", "hours": 5}, "B", 403, NOT_AUTHORIZED),
    ("POST", "/games/{gid}/deadline/propose", {"power": "FRANCE", "hours": 5}, "C", 403, NOT_AUTHORIZED),
    ("POST", "/games/set_orders", {"game_id": "{gid}", "power": "FRANCE", "orders": ["A PAR - BUR"]}, "B", 403, NOT_AUTHORIZED),
    ("POST", "/games/set_orders", {"game_id": "{gid}", "power": "FRANCE", "orders": ["A PAR - BUR"]}, "C", 403, NOT_AUTHORIZED),
    ("POST", "/games/{gid}/quit", {"power": "FRANCE"}, "B", 403, "You are not authorized to quit this power."),
    ("POST", "/games/{gid}/quit", {}, "C", 404, "Player not found in game"),
    ("GET", "/games/{gid}/orders/FRANCE", None, "B", 403, "You are not authorized to view orders for this power."),
    ("GET", "/games/{gid}/orders/FRANCE", None, "C", 403, "You are not authorized to view orders for this power."),
    ("GET", "/games/{gid}/orders/FRANCE", None, "", 403, "You are not authorized to view orders for this power."),
]

MEMBERS_ONLY = [
    # Any player may act, a non-member may not.
    ("POST", "/games/{gid}/auto_process", {"enabled": True}, "C", 403, NOT_PLAYER),
    ("POST", "/games/{gid}/deadline", {"phase_length_seconds": 3600}, "C", 403, NOT_PLAYER),
    ("POST", "/games/{gid}/deadline/schedule", {"schedule": "Mon 16:00"}, "C", 403, NOT_PLAYER),
    ("POST", "/games/{gid}/snapshot", None, "C", 403, NOT_PLAYER),
]

CREATOR_ONLY = [
    # Seated, but not the creator: 403 with the creator-only message.
    ("POST", "/games/{gid}/join_password", {"join_password": "secret1"}, "B", 403, "Only the game's creator can change its join password."),
    ("POST", "/games/{gid}/join_password", {"join_password": "secret1"}, "C", 403, "Only the game's creator can change its join password."),
    ("POST", "/games/{gid}/dummies", {"power": "ITALY", "dummy": True}, "B", 403, "Only the game's creator can change its dummy powers."),
    ("POST", "/games/{gid}/dummies", {"power": "ITALY", "dummy": True}, "C", 403, "Only the game's creator can change its dummy powers."),
    ("POST", "/games/{gid}/process_turn", None, "C", 403, "Only the game's creator can end a turn early. The turn is processed at the deadline, or as soon as every order is in if auto-process is on."),
    ("POST", "/games/{gid}/restore/1", None, "C", 403, "Admin token required to restore a snapshot"),
]


@pytest.mark.parametrize("case", POWER_BOUND + MEMBERS_ONLY + CREATOR_ONLY, ids=lambda c: f"{c[0]} {c[1]} as {c[3] or 'anon'} -> {c[4]}")
def test_authorization_refusals(client: TestClient, table: Dict[str, Any], case: Any) -> None:
    method, path, body, who, status, detail = case
    if isinstance(body, dict) and "game_id" in body:
        body = {**body, "game_id": table["gid"]}
    _check(client, table, method, path, body, who, status, detail)


GAME_BOUND_404 = [
    ("POST", "/games/{gid}/join_password", {"join_password": "x"}, "Game not found"),
    ("POST", "/games/{gid}/auto_process", {"enabled": True}, "Game not found"),
    ("POST", "/games/{gid}/dummies", {"power": "ITALY"}, "Game not found"),
    ("POST", "/games/{gid}/deadline", {"phase_length_seconds": 3600}, "Game not found"),
    ("POST", "/games/{gid}/process_turn", None, "Game not found"),
    ("GET", "/games/{gid}/orders", None, "Game not found"),
    ("GET", "/games/{gid}/orders/FRANCE", None, "Game not found"),
    ("GET", "/games/{gid}/orders/history", None, "Game not found"),
    ("POST", "/games/{gid}/wait", {"power": "FRANCE"}, f"Game {NO_GAME} not found"),
    ("POST", "/games/{gid}/draw_vote", {"power": "FRANCE", "vote": True}, f"Game {NO_GAME} not found"),
    ("POST", "/games/{gid}/concede", {"power": "FRANCE"}, f"Game {NO_GAME} not found"),
    ("POST", "/games/{gid}/deadline/propose", {"power": "FRANCE", "hours": 5}, f"Game {NO_GAME} not found"),
    ("POST", "/games/{gid}/deadline/vote", {"power": "FRANCE", "vote": True}, f"Game {NO_GAME} not found"),
    ("POST", "/games/set_orders", {"game_id": NO_GAME, "power": "FRANCE", "orders": ["A PAR - BUR"]}, f"Game {NO_GAME} not found"),
    ("POST", "/games/{gid}/message", {"recipient_power": "FRANCE", "text": "hi"}, "Game not found"),
    ("POST", "/games/{gid}/broadcast", {"text": "hi"}, "Game not found"),
    ("GET", "/games/{gid}/messages", None, "Game not found"),
]


@pytest.mark.parametrize("case", GAME_BOUND_404, ids=lambda c: f"{c[0]} {c[1]}")
def test_missing_game_is_404_not_500(client: TestClient, table: Dict[str, Any], case: Any) -> None:
    method, path, body, detail = case
    r = client.request(method, path.format(gid=NO_GAME), json=body, headers=table["A"])
    assert (r.status_code, r.json().get("detail")) == (404, detail), r.text


def test_deadline_proposal_with_nothing_pending_is_400(client: TestClient, table: Dict[str, Any]) -> None:
    gid = table["gid"]
    for path, body in (("vote", {"power": "FRANCE", "vote": True}), ("withdraw", {"power": "FRANCE"})):
        r = client.post(f"/games/{gid}/deadline/{path}", json=body, headers=table["A"])
        assert (r.status_code, r.json()["detail"]) == (400, f"No deadline proposal is pending in game {gid}")


def test_orders_listing_is_only_the_callers_own_power(client: TestClient, table: Dict[str, Any]) -> None:
    gid = table["gid"]
    set_a = client.post("/games/set_orders", json={"game_id": gid, "power": "FRANCE", "orders": ["A PAR - BUR"]}, headers=table["A"])
    assert set_a.status_code == 200, set_a.text
    mine = client.get(f"/games/{gid}/orders", headers=table["A"]).json()
    assert [(o["power"], o["order"]) for o in mine] == [("FRANCE", "A PAR - BUR")]
    # A seated rival and an outsider both see nothing of France's orders.
    assert [o for o in client.get(f"/games/{gid}/orders", headers=table["B"]).json() if o["power"] == "FRANCE"] == []
    assert client.get(f"/games/{gid}/orders", headers=table["C"]).json() == []
    assert client.get(f"/games/{gid}/orders").json() == []
    own = client.get(f"/games/{gid}/orders/FRANCE", headers=table["A"]).json()
    assert own == {"power": "FRANCE", "orders": ["A PAR - BUR"]}


def test_wait_flag_by_owner_succeeds_and_a_conceded_power_cannot_broadcast(client: TestClient) -> None:
    a, b = _user(client), _user(client)
    gid = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=a).json()["game_id"]
    assert client.post(f"/games/{gid}/join", json={"power": "FRANCE"}, headers=a).status_code == 200
    assert client.post(f"/games/{gid}/join", json={"power": "ENGLAND"}, headers=b).status_code == 200
    fill_with_dummies(gid)
    ok = client.post(f"/games/{gid}/wait", json={"power": "FRANCE", "waiting": True}, headers=a)
    assert (ok.status_code, ok.json()["waiting"]) == (200, ["FRANCE"])
    conceded = client.post(f"/games/{gid}/concede", json={"power": "FRANCE"}, headers=a)
    assert conceded.status_code == 200, conceded.text
    # The concession left the table (BL2): France can no longer write messages.
    msg = client.post(f"/games/{gid}/broadcast", json={"text": "gg"}, headers=a)
    assert msg.status_code == 409, msg.text


class TestMessagePrivacy:
    def test_non_member_cannot_send(self, client: TestClient, table: Dict[str, Any]) -> None:
        gid = table["gid"]
        for path, body in (("message", {"recipient_power": "FRANCE", "text": "hi"}), ("broadcast", {"text": "hi"})):
            r = client.post(f"/games/{gid}/{path}", json=body, headers=table["C"])
            assert (r.status_code, r.json()["detail"]) == (403, "Sender not in game")

    def test_private_mail_is_seen_only_by_its_two_ends(self, client: TestClient, table: Dict[str, Any]) -> None:
        gid = table["gid"]
        priv = client.post(f"/games/{gid}/message", json={"recipient_power": "ENGLAND", "text": "cw-secret-pact"}, headers=table["A"])
        assert priv.status_code == 200, priv.text
        bc = client.post(f"/games/{gid}/broadcast", json={"text": "cw-public-note"}, headers=table["A"])
        assert bc.status_code == 200, bc.text

        def texts(headers: Dict[str, str]) -> set:
            r = client.get(f"/games/{gid}/messages", headers=headers)
            assert r.status_code == 200, r.text
            return {m["text"] for m in r.json()["messages"]}

        both = {"cw-secret-pact", "cw-public-note"}
        assert texts(table["A"]) == both
        assert texts(table["B"]) == both
        # A third player, an outsider and an anonymous reader get the broadcast only.
        assert texts(table["D"]) == {"cw-public-note"}
        assert texts(table["C"]) == {"cw-public-note"}
        assert texts({}) == {"cw-public-note"}

    def test_private_message_to_unseated_or_unknown_power_is_400(self, client: TestClient, table: Dict[str, Any]) -> None:
        gid = table["gid"]
        typo = client.post(f"/games/{gid}/message", json={"recipient_power": "FRANC", "text": "hi"}, headers=table["A"])
        assert (typo.status_code, typo.json()["detail"]) == (
            400,
            "FRANC is not a power. The powers are AUSTRIA, ENGLAND, FRANCE, GERMANY, ITALY, RUSSIA, TURKEY.",
        )
        own = client.post(f"/games/{gid}/message", json={"recipient_power": "FRANCE", "text": "hi"}, headers=table["A"])
        assert (own.status_code, own.json()["detail"]) == (400, "You play FRANCE: a private message goes to another power.")
