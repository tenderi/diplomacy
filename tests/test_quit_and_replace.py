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

from server.api import app
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


class TestJoinCompletedGame:
    def test_join_refused_once_the_game_has_ended(self, client):
        from engine.serialization import state_to_dict
        from engine.types import GameState, Location, PhaseType, Season, Unit, UnitKind
        from server.api.shared import game_service

        game_id, _a = _game_with_france(client)
        state = GameState(
            1901, Season.SPRING, PhaseType.MOVEMENT,
            units=frozenset({Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))}),
            ownership={"PAR": "FRANCE"},
        )
        game_service.restore_snapshot(game_id, state_to_dict(state), phase_code="S1901M")
        assert game_service.submit_draw_vote(game_id, "FRANCE", True)["quorum_reached"] is True
        b = _telegram_user(client, "late")
        r = client.post(f"/games/{game_id}/join", json=_as(b, power="GERMANY"))
        assert r.status_code == 409, r.text


class TestMessagingAndVacantSeats:
    def test_private_message_to_a_vacated_seat_is_refused(self, client):
        game_id, a = _game_with_france(client)
        b = _telegram_user(client, "leaver")
        assert client.post(f"/games/{game_id}/join", json=_as(b, power="GERMANY")).status_code == 200
        assert client.post(f"/games/{game_id}/quit", json=_as(b)).status_code == 200
        r = client.post(f"/games/{game_id}/message", json=_as(a, recipient_power="GERMANY", text="anyone there?"))
        assert r.status_code == 400, r.text
        assert "no player is assigned" in r.json()["detail"]

    def test_power_names_are_case_insensitive_on_every_seat_lookup(self, client):
        game_id, a = _game_with_france(client)
        b = _telegram_user(client, "reader")
        assert client.post(f"/games/{game_id}/join", json=_as(b, power="GERMANY")).status_code == 200
        # Orders for "france"...
        r = client.post("/games/set_orders", json=_as(a, game_id=game_id, power="france", orders=["A PAR H"]))
        assert r.status_code == 200, r.text
        # ...and a private message to "germany", stored upper-cased so the
        # recipient's inbox filter (which compares against GERMANY) finds it.
        r = client.post(f"/games/{game_id}/message", json=_as(a, recipient_power="germany", text="psst"))
        assert r.status_code == 200, r.text
        inbox = client.get(f"/games/{game_id}/messages", params={"telegram_id": b, "bot_secret": BOT_SECRET}).json()["messages"]
        assert [m["text"] for m in inbox if m["recipient_power"] == "GERMANY"] == ["psst"]


class TestRoutesDoNotWrapTheirOwn404s:
    """``except Exception`` handlers used to catch the route's own ``HTTPException``
    and re-raise it as a 500 with the real status embedded in the text."""

    def test_players_of_missing_game_is_404(self, client):
        r = client.get("/games/nonexistent/players")
        assert r.status_code == 404, r.text

    def test_history_of_missing_turn_is_404(self, client):
        game_id, _a = _game_with_france(client)
        r = client.get(f"/games/{game_id}/history/99")
        assert r.status_code == 404, r.text


class TestRestoreIsAdminOnly:
    """Track R: ``POST /games/{id}/restore/{snapshot_id}`` rewinds a game and used
    to take no credentials at all -- and nginx proxies ``/api/`` to the internet."""

    ADMIN = {"X-Admin-Token": "changeme"}  # conftest's default admin token
    BOT = {"X-Bot-Secret": BOT_SECRET}

    def _game_with_snapshot(self, client):
        game_id, a = _game_with_france(client)
        snap = client.post(f"/games/{game_id}/snapshot", headers=self.BOT)
        assert snap.status_code == 200, snap.text
        snapshot_id = snap.json()["snapshot_id"]
        # Move the game on: process S1901M -> F1901M, leave a pending order.
        assert client.post(f"/games/{game_id}/process_turn", headers=self.BOT).status_code == 200
        assert client.get(f"/games/{game_id}/state").json()["phase"] == "F1901M"
        assert client.post("/games/set_orders", json=_as(a, game_id=game_id, power="FRANCE", orders=["A PAR H"])).status_code == 200
        return game_id, snapshot_id

    def test_anonymous_and_ordinary_users_are_refused(self, client):
        game_id, snapshot_id = self._game_with_snapshot(client)
        assert client.post(f"/games/{game_id}/restore/{snapshot_id}").status_code == 403
        assert client.post(f"/games/{game_id}/restore/{snapshot_id}", headers=self.BOT).status_code == 403
        assert client.post(f"/games/{game_id}/restore/{snapshot_id}", headers={"X-Admin-Token": "wrong"}).status_code == 403
        assert client.get(f"/games/{game_id}/state").json()["phase"] == "F1901M"  # untouched

    def test_admin_restore_rewinds_clears_orders_and_tells_players(self, client):
        from tests.reliability_helpers import OutboxProbe

        game_id, snapshot_id = self._game_with_snapshot(client)
        with OutboxProbe() as probe:
            r = client.post(f"/games/{game_id}/restore/{snapshot_id}", headers=self.ADMIN)
            assert r.status_code == 200, r.text
            texts = probe.messages()
        state = client.get(f"/games/{game_id}/state").json()
        assert state["phase"] == "S1901M"
        assert state["orders"] == {}
        assert any("rolled back" in t and "S1901M" in t for t in texts)

    def test_snapshot_and_generate_map_need_a_caller(self, client):
        game_id, _a = _game_with_france(client)
        assert client.post(f"/games/{game_id}/snapshot").status_code == 401
        assert client.post(f"/games/{game_id}/generate_map").status_code == 401
        assert client.post(f"/games/{game_id}/generate_map", headers=self.BOT).status_code == 200
