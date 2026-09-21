"""Track L: every write route refuses a game that has already ended (409).

Before this, a COMPLETED game still accepted orders (stored and shown as
pending), ``process_turn`` "succeeded" with an empty resolution and DMed every
player "turn processed", a draw vote was "recorded", and ``concede`` removed a
power's units from the *final* board. ``orders_status`` also listed players as
"missing" on a finished game, so the bot's ``/status`` said it was waiting on
them.
"""
import time

import pytest
from fastapi.testclient import TestClient

from engine.serialization import state_to_dict
from engine.types import GameState, Location, PhaseType, Season, Unit, UnitKind
from server.api import app
from server.api.shared import game_service
from tests.conftest import _get_db_url

BOT_SECRET = "test_bot_secret_for_tests"

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


@pytest.fixture
def client():
    return TestClient(app)


def _register_and_login(client, prefix):
    email = f"{prefix}_{int(time.time() * 1000)}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert reg.status_code == 200, reg.text
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


def _drawn_game(client) -> tuple[str, str]:
    """A game FRANCE (held by ``tg``) and GERMANY have just drawn.

    Returns ``(game_id, telegram_id)``. The board is shrunk to two powers via
    ``restore_snapshot`` so a two-vote draw completes it through the real
    ``submit_draw_vote`` path (status persisted by ``save_state``).
    """
    tg = f"go_{int(time.time() * 1000)}"
    client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": tg, "full_name": "Over"})
    headers = _register_and_login(client, "gameover")
    game_id = client.post("/games/create", json={"map_name": "standard"}, headers=headers).json()["game_id"]
    join = client.post(
        f"/games/{int(game_id)}/join",
        json={"telegram_id": tg, "bot_secret": BOT_SECRET, "game_id": int(game_id), "power": "FRANCE"},
    )
    assert join.status_code == 200, join.text

    state = GameState(
        1901, Season.SPRING, PhaseType.MOVEMENT,
        units=frozenset({
            Unit(UnitKind.ARMY, "FRANCE", Location("PAR")),
            Unit(UnitKind.ARMY, "GERMANY", Location("MUN")),
        }),
        ownership={"PAR": "FRANCE", "MUN": "GERMANY"},
    )
    game_service.restore_snapshot(game_id, state_to_dict(state), phase_code="S1901M")
    game_service.submit_draw_vote(game_id, "FRANCE", True)
    out = game_service.submit_draw_vote(game_id, "GERMANY", True)
    assert out["quorum_reached"] is True
    assert client.get(f"/games/{game_id}/state").json()["status"] == "COMPLETED"
    return game_id, tg


def _as_france(tg: str, **extra) -> dict:
    return {"telegram_id": tg, "bot_secret": BOT_SECRET, "power": "FRANCE", **extra}


class TestWritesRefusedOnCompletedGame:
    def test_set_orders_is_409_and_nothing_is_stored(self, client):
        game_id, tg = _drawn_game(client)
        resp = client.post("/games/set_orders", json=_as_france(tg, game_id=game_id, orders=["A PAR H"]))
        assert resp.status_code == 409, resp.text
        assert "drawn between FRANCE, GERMANY" in resp.json()["detail"]
        assert client.get(f"/games/{game_id}/state").json()["orders"] == {}

    def test_process_turn_is_409_and_the_board_is_untouched(self, client):
        game_id, _tg = _drawn_game(client)
        before = client.get(f"/games/{game_id}/state").json()
        resp = client.post(f"/games/{game_id}/process_turn", headers={"X-Bot-Secret": BOT_SECRET})
        assert resp.status_code == 409, resp.text
        after = client.get(f"/games/{game_id}/state").json()
        assert (after["phase"], after["units"], after["winners"]) == (before["phase"], before["units"], before["winners"])

    def test_draw_vote_is_409(self, client):
        game_id, tg = _drawn_game(client)
        resp = client.post(f"/games/{game_id}/draw_vote", json=_as_france(tg, vote=True))
        assert resp.status_code == 409, resp.text

    def test_concede_is_409_and_keeps_the_final_board(self, client):
        game_id, tg = _drawn_game(client)
        resp = client.post(f"/games/{game_id}/concede", json=_as_france(tg))
        assert resp.status_code == 409, resp.text
        units = client.get(f"/games/{game_id}/state").json()["units"]
        assert {u["power"] for u in units} == {"FRANCE", "GERMANY"}

    def test_orders_status_waits_on_nobody(self, client):
        game_id, _tg = _drawn_game(client)
        status = client.get(f"/games/{game_id}/orders_status").json()
        assert status["active_powers"] == []
        assert status["missing"] == []

    def test_reads_still_work(self, client):
        game_id, _tg = _drawn_game(client)
        assert client.get(f"/games/{game_id}/state").status_code == 200
        assert client.get(f"/games/{game_id}/draw_vote_status").status_code == 200
        assert client.get(f"/games/{game_id}/legal_orders/FRANCE").status_code == 200
