"""Random-powers games: joining players don't choose -- the server deals each
an open power.

Fixed at creation. A join must leave out ``power`` and is told the power it got;
dummies are never dealt; /replace (which names a power) is refused, since /join
takes over a vacant seat too, at random.
"""
import time

import pytest
from fastapi.testclient import TestClient

from server.api import app
from tests.conftest import _get_db_url

BOT_SECRET = "test_bot_secret_for_tests"
POWERS = {"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"}

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

_BOT = {"X-Bot-Secret": BOT_SECRET}
_tg_seq = 0


@pytest.fixture
def client():
    return TestClient(app)


def _telegram_user(client):
    global _tg_seq
    _tg_seq += 1
    tg = str(int(time.time() * 1000) % 10**9 * 10 + _tg_seq % 10)
    r = client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": tg})
    assert r.status_code == 200, r.text
    return tg


def _as(tg, **extra):
    return {"telegram_id": tg, "bot_secret": BOT_SECRET, **extra}


def _game(client, **settings):
    creator = _telegram_user(client)
    r = client.post("/games/create", json={"map_name": "standard", **settings, **_as(creator)}, headers=_BOT)
    assert r.status_code == 200, r.text
    return str(r.json()["game_id"])


def _join(client, game_id, tg, **extra):
    return client.post(f"/games/{game_id}/join", json=_as(tg, **extra))


def _listed(client, game_id):
    return next(g for g in client.get("/games").json()["games"] if str(g["game_id"]) == game_id)


class TestTheSettingIsStored:
    def test_players_choose_unless_the_game_is_created_random(self, client):
        game_id = _game(client)
        assert client.get(f"/games/{game_id}/state").json()["random_powers"] is False
        assert _listed(client, game_id)["random_powers"] is False

    def test_a_random_powers_game_says_so(self, client):
        game_id = _game(client, random_powers=True)
        assert client.get(f"/games/{game_id}/state").json()["random_powers"] is True
        assert _listed(client, game_id)["random_powers"] is True


class TestJoining:
    def test_each_join_is_dealt_a_different_open_power(self, client):
        game_id = _game(client, random_powers=True)
        dealt = []
        for _ in range(7):
            r = _join(client, game_id, _telegram_user(client))
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "ok"
            dealt.append(r.json()["power"])
        assert set(dealt) == POWERS
        seats = {p["power"]: p["seated"] for p in _listed(client, game_id)["players"]}
        assert seats == {p: True for p in POWERS}
        r = _join(client, game_id, _telegram_user(client))
        assert r.status_code == 409
        assert r.json()["detail"] == f"Game {game_id} is full: every power is taken."

    def test_civil_disorder_powers_are_never_dealt(self, client):
        dummies = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA"]
        game_id = _game(client, random_powers=True, dummy_powers=dummies)
        r = _join(client, game_id, _telegram_user(client))
        assert r.status_code == 200, r.text
        assert r.json()["power"] == "TURKEY"

    def test_choosing_a_power_is_refused(self, client):
        game_id = _game(client, random_powers=True)
        r = _join(client, game_id, _telegram_user(client), power="FRANCE")
        assert r.status_code == 400
        assert r.json()["detail"] == f"Powers are assigned at random in game {game_id}: join without choosing one."

    def test_a_second_join_reports_the_power_already_held(self, client):
        game_id = _game(client, random_powers=True)
        tg = _telegram_user(client)
        first = _join(client, game_id, tg).json()
        again = _join(client, game_id, tg).json()
        assert again["status"] == "already_joined"
        assert again["power"] == first["power"]

    def test_a_vacated_seat_is_dealt_again(self, client):
        dummies = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY"]
        game_id = _game(client, random_powers=True, dummy_powers=dummies)
        leaver, stayer = _telegram_user(client), _telegram_user(client)
        left = _join(client, game_id, leaver).json()["power"]
        kept = _join(client, game_id, stayer).json()["power"]
        assert {left, kept} == {"RUSSIA", "TURKEY"}
        assert client.post(f"/games/{game_id}/quit", json=_as(leaver)).status_code == 200
        r = _join(client, game_id, _telegram_user(client))
        assert r.status_code == 200, r.text
        assert r.json()["power"] == left

    def test_replace_is_refused(self, client):
        game_id = _game(client, random_powers=True)
        r = client.post(f"/games/{game_id}/replace", json=_as(_telegram_user(client), power="FRANCE"))
        assert r.status_code == 400
        assert r.json()["detail"] == (
            f"Powers are assigned at random in game {game_id}: use join, which seats you in an open power."
        )


class TestAChoosingGame:
    def test_a_join_must_name_a_power(self, client):
        game_id = _game(client)
        r = _join(client, game_id, _telegram_user(client))
        assert r.status_code == 400
        assert r.json()["detail"] == "Choose a power to join as."

    def test_the_join_reply_names_the_chosen_power(self, client):
        game_id = _game(client)
        r = _join(client, game_id, _telegram_user(client), power="france")
        assert r.status_code == 200, r.text
        assert r.json()["power"] == "FRANCE"
