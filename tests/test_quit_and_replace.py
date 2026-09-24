"""Track P: quitting actually vacates the seat, and the seat can be filled again.

Until v2.7.75 both ``/quit`` and ``/replace`` assigned ``player.user_id`` on the
detached row ``get_player_by_game_id_and_power`` returns and then called the
no-op ``DatabaseService.commit()`` -- so ``is_active`` changed and ``user_id``
silently did not. A quitter still held the power (orders, draw votes and
concession all authorized), ``/replace`` refused with "already assigned"
(wrapped in a 500), and the quitter's own re-join said "already_joined".
"""
import time

import pytest
from fastapi.testclient import TestClient

from server.api import ADMIN_TOKEN, app
from server.api.shared import db_service
from tests.conftest import _get_db_url

BOT_SECRET = "test_bot_secret_for_tests"

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


@pytest.fixture
def client():
    return TestClient(app)


def _register_and_login(client, prefix):
    email = f"{prefix}_{int(time.time() * 1000000)}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert reg.status_code == 200, reg.text
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


_tg_seq = 0


def _telegram_user(client, name):
    # Numeric, like a real Telegram id: ``notify_players`` skips non-numeric ids.
    global _tg_seq
    _tg_seq += 1
    tg = str(int(time.time() * 1000) % 10**9 * 10 + _tg_seq % 10)
    r = client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": tg, "full_name": name})
    assert r.status_code == 200, r.text
    return tg


def _game_with_france(client):
    """A game where telegram user ``a`` holds FRANCE. Returns ``(game_id, a)``."""
    headers = _register_and_login(client, "qr")
    game_id = client.post("/games/create", json={"map_name": "standard"}, headers=headers).json()["game_id"]
    a = _telegram_user(client, "quitter")
    r = client.post(f"/games/{game_id}/join", json={"telegram_id": a, "bot_secret": BOT_SECRET, "power": "FRANCE"})
    assert r.status_code == 200 and r.json()["status"] == "ok", r.text
    return game_id, a


def _seat(client, game_id, power):
    return next(p for p in client.get(f"/games/{game_id}/players").json() if p["power"] == power)


def _as(tg, **extra):
    return {"telegram_id": tg, "bot_secret": BOT_SECRET, **extra}


_BOT = {"X-Bot-Secret": BOT_SECRET}


class TestQuit:
    BOT = _BOT

    def test_quit_clears_user_id_and_marks_inactive(self, client):
        game_id, a = _game_with_france(client)
        r = client.post(f"/games/{game_id}/quit", json=_as(a))
        assert r.status_code == 200, r.text
        seat = _seat(client, game_id, "FRANCE")
        assert seat["user_id"] is None
        assert seat["is_active"] is False
        # The DAL agrees (no cache in between).
        row = db_service.get_player_by_game_id_and_power(game_id=int(game_id), power="FRANCE")
        assert row.user_id is None and row.is_active is False

    def test_quitter_can_no_longer_act_for_the_power(self, client):
        game_id, a = _game_with_france(client)
        assert client.post(f"/games/{game_id}/quit", json=_as(a)).status_code == 200
        assert client.post("/games/set_orders", json=_as(a, game_id=game_id, power="FRANCE", orders=["A PAR H"])).status_code == 403
        assert client.post(f"/games/{game_id}/draw_vote", json=_as(a, power="FRANCE", vote=True)).status_code == 403
        assert client.post(f"/games/{game_id}/concede", json=_as(a, power="FRANCE")).status_code == 403
        assert client.post(f"/games/{game_id}/quit", json=_as(a, power="FRANCE")).status_code == 403
        assert client.get(f"/users/{a}/games", headers=self.BOT).json()["games"] == []

    def test_pending_orders_survive_a_quit_for_the_replacement(self, client):
        game_id, a = _game_with_france(client)
        r = client.post("/games/set_orders", json=_as(a, game_id=game_id, power="FRANCE", orders=["A PAR - BUR"]))
        assert r.status_code == 200
        client.post(f"/games/{game_id}/quit", json=_as(a))
        assert client.get(f"/games/{game_id}/state").json()["orders"] == {"FRANCE": ["A PAR - BUR"]}


class TestFillingAVacatedSeat:
    BOT = _BOT

    def test_replace_assigns_the_new_user(self, client):
        game_id, a = _game_with_france(client)
        client.post(f"/games/{game_id}/quit", json=_as(a))
        b = _telegram_user(client, "replacer")
        r = client.post(f"/games/{game_id}/replace", json=_as(b, power="FRANCE"))
        assert r.status_code == 200, r.text
        seat = _seat(client, game_id, "FRANCE")
        assert seat["user_id"] is not None and seat["is_active"] is True
        # The replacement holds the power; the quitter does not.
        assert client.post("/games/set_orders", json=_as(b, game_id=game_id, power="FRANCE", orders=["A PAR H"])).status_code == 200
        assert client.post("/games/set_orders", json=_as(a, game_id=game_id, power="FRANCE", orders=["A PAR H"])).status_code == 403
        assert client.get(f"/users/{b}/games", headers=self.BOT).json()["games"][0]["power"] == "FRANCE"

    def test_join_takes_over_a_vacant_seat(self, client):
        """The web client lists a vacated seat as "Open" and offers it in the
        join dropdown; that must not come back as 409 "Power already taken"."""
        game_id, a = _game_with_france(client)
        client.post(f"/games/{game_id}/quit", json=_as(a))
        b = _telegram_user(client, "joiner")
        r = client.post(f"/games/{game_id}/join", json=_as(b, power="FRANCE"))
        assert r.status_code == 200 and r.json()["status"] == "ok", r.text
        assert _seat(client, game_id, "FRANCE")["user_id"] is not None
        # And only one FRANCE row exists -- the seat was reused, not duplicated.
        assert [p["power"] for p in client.get(f"/games/{game_id}/players").json()].count("FRANCE") == 1

    def test_quitter_can_come_back(self, client):
        game_id, a = _game_with_france(client)
        client.post(f"/games/{game_id}/quit", json=_as(a))
        r = client.post(f"/games/{game_id}/join", json=_as(a, power="FRANCE"))
        assert r.status_code == 200 and r.json()["status"] == "ok", r.text
        assert client.post("/games/set_orders", json=_as(a, game_id=game_id, power="FRANCE", orders=["A PAR H"])).status_code == 200

    def test_replace_of_a_held_seat_is_400_not_500(self, client):
        game_id, _a = _game_with_france(client)
        b = _telegram_user(client, "intruder")
        r = client.post(f"/games/{game_id}/replace", json=_as(b, power="FRANCE"))
        assert r.status_code == 400, r.text
        assert "already assigned" in r.json()["detail"]

    def test_join_of_a_held_seat_is_still_409(self, client):
        game_id, _a = _game_with_france(client)
        b = _telegram_user(client, "latecomer")
        r = client.post(f"/games/{game_id}/join", json=_as(b, power="FRANCE"))
        assert r.status_code == 409

    def test_replace_needs_a_real_vacated_seat_and_a_newcomer(self, client):
        game_id, a = _game_with_france(client)
        b = _telegram_user(client, "newcomer")
        # GERMANY was never taken: there is no seat row to take over.
        assert client.post(f"/games/{game_id}/replace", json=_as(b, power="GERMANY")).status_code == 404
        client.post(f"/games/{game_id}/quit", json=_as(a))
        assert client.post(f"/games/{game_id}/join", json=_as(b, power="ENGLAND")).status_code == 200
        r = client.post(f"/games/{game_id}/replace", json=_as(b, power="FRANCE"))
        assert (r.status_code, r.json()["detail"]) == (400, "User is already in the game")

    def test_an_admin_marks_a_seat_inactive_once(self, client):
        game_id, _a = _game_with_france(client)
        path = f"/games/{game_id}/players/FRANCE/mark_inactive"
        assert client.post(path, json={"admin_token": ADMIN_TOKEN}).json()["status"] == "ok"
        assert client.post(path, json={"admin_token": ADMIN_TOKEN}).json() == {"status": "already_inactive"}
        assert client.post(f"/games/{game_id}/players/ITALY/mark_inactive", json={"admin_token": ADMIN_TOKEN}).status_code == 404


class TestJoinAndQuitRefusals:
    def test_join_names_an_unknown_power(self, client):
        game_id, _a = _game_with_france(client)
        b = _telegram_user(client, "atlantean")
        r = client.post(f"/games/{game_id}/join", json=_as(b, power="ATLANTIS"))
        assert (r.status_code, r.json()["detail"]) == (400, "Invalid power name: ATLANTIS")

    def test_quitting_a_game_you_are_not_in(self, client):
        game_id, _a = _game_with_france(client)
        b = _telegram_user(client, "stranger")
        assert client.post(f"/games/{game_id}/quit", json=_as(b)).json()["detail"] == "Player not found in game"
        assert client.post(f"/games/{game_id}/quit", json=_as(b, power="ITALY")).json()["detail"] == "Power not found in game"


class TestProcessTurnRequireAll:
    def test_refuses_naming_who_has_not_ordered(self, client):
        game_id, a = _game_with_france(client)
        client.post("/games/set_orders", json=_as(a, game_id=game_id, power="FRANCE", orders=["A PAR H", "A MAR H", "F BRE H"]))
        r = client.post(f"/games/{game_id}/process_turn?require_all=true", headers=_BOT)
        assert r.status_code == 400
        # Empty seats still have units to order; only civil-disorder dummies are never waited on.
        for power in ("AUSTRIA", "ENGLAND", "GERMANY", "ITALY", "RUSSIA", "TURKEY"):
            assert power in r.json()["detail"]
        assert "FRANCE" not in r.json()["detail"]

    def test_runs_once_every_non_dummy_power_has_ordered(self, client):
        others = ["AUSTRIA", "ENGLAND", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]
        a = _telegram_user(client, "soloist")
        game_id = client.post("/games/create", json=_as(a, map_name="standard", dummy_powers=others), headers=_BOT).json()["game_id"]
        assert client.post(f"/games/{game_id}/join", json=_as(a, power="FRANCE")).status_code == 200
        path = f"/games/{game_id}/process_turn?require_all=true"
        assert client.post(path, headers=_BOT).status_code == 400
        client.post("/games/set_orders", json=_as(a, game_id=game_id, power="FRANCE", orders=["A PAR H", "A MAR H", "F BRE H"]))
        assert client.post(path, headers=_BOT).status_code == 200
