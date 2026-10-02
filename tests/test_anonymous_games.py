"""Anonymous and public games: who a player is known as.

A game is created anonymous or public and stays that way. Anonymous: every
announcement and relayed message names the power alone, and no API read says
who holds a seat -- not the nickname, the Telegram id, or the numeric user id (a
public game's player list would map that straight back to a nickname). Public:
the player's nickname rides along with the power.
"""
import time

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api.shared import db_service
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe

BOT_SECRET = "test_bot_secret_for_tests"

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

_BOT = {"X-Bot-Secret": BOT_SECRET}
_tg_seq = 0


@pytest.fixture
def client():
    return TestClient(app)


def _telegram_user(client, name):
    """A registered Telegram player with the nickname ``name`` plus a per-run
    suffix (nicknames are unique). Returns ``(telegram_id, nickname)``."""
    # Numeric, like a real Telegram id: ``notify_players`` skips non-numeric ids.
    global _tg_seq
    _tg_seq += 1
    tg = str(int(time.time() * 1000) % 10**9 * 10 + _tg_seq % 10)
    r = client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": tg})
    assert r.status_code == 200, r.text
    nickname = f"{name}{tg[-7:]}"
    r = client.post("/users/nickname", json={"bot_secret": BOT_SECRET, "telegram_id": tg, "nickname": nickname})
    assert r.status_code == 200, r.text
    return tg, nickname


def _as(tg, **extra):
    return {"telegram_id": tg, "bot_secret": BOT_SECRET, **extra}


def _game(client, *, anonymous):
    """A game where Anna holds FRANCE and Bert GERMANY.
    Returns ``(game_id, anna_telegram_id, bert_telegram_id, bert_nickname)``."""
    (anna, _), (bert, bert_nick) = _telegram_user(client, "Anna"), _telegram_user(client, "Bert")
    r = client.post("/games/create", json={"map_name": "standard", "anonymous": anonymous, **_as(anna)}, headers=_BOT)
    assert r.status_code == 200, r.text
    game_id = str(r.json()["game_id"])
    for tg, power in ((anna, "FRANCE"), (bert, "GERMANY")):
        r = client.post(f"/games/{game_id}/join", json=_as(tg, power=power))
        assert r.status_code == 200 and r.json()["status"] == "ok", r.text
    return game_id, anna, bert, bert_nick


def _label(anonymous, power, nickname):
    return power if anonymous else f"{power} ({nickname})"


def _listed(client, game_id):
    return next(g for g in client.get("/games").json()["games"] if str(g["game_id"]) == game_id)


class TestTheSettingIsStored:
    def test_a_game_is_public_unless_created_anonymous(self, client):
        tg, _ = _telegram_user(client, "Creator")
        game_id = str(client.post("/games/create", json={"map_name": "standard", **_as(tg)}, headers=_BOT).json()["game_id"])
        assert client.get(f"/games/{game_id}/state").json()["anonymous"] is False
        assert _listed(client, game_id)["anonymous"] is False

    def test_an_anonymous_game_says_so(self, client):
        game_id, *_ = _game(client, anonymous=True)
        assert client.get(f"/games/{game_id}/state").json()["anonymous"] is True
        assert _listed(client, game_id)["anonymous"] is True


class TestWhoHoldsASeat:
    def test_an_anonymous_game_shows_seats_but_never_who_holds_them(self, client):
        game_id, *_ = _game(client, anonymous=True)
        seats = {p["power"]: p for p in client.get(f"/games/{game_id}/players").json()}
        assert seats["FRANCE"] == {
            "power": "FRANCE", "seated": True, "user_id": None, "is_active": True,
            "nickname": None,
        }
        assert {p["power"]: (p["seated"], p["user_id"]) for p in _listed(client, game_id)["players"]} == {
            "FRANCE": (True, None), "GERMANY": (True, None),
        }
        state_seats = client.get(f"/games/{game_id}/state").json()["players"]
        assert state_seats["GERMANY"] == {"user_id": None, "is_active": True, "seated": True}

    def test_a_public_game_names_each_seat(self, client):
        game_id, anna, _bert, bert_nick = _game(client, anonymous=False)
        seats = {p["power"]: p for p in client.get(f"/games/{game_id}/players").json()}
        assert seats["GERMANY"]["nickname"] == bert_nick
        # A public game names a seat by nickname, never by its Telegram account.
        assert sorted(seats["FRANCE"]) == ["is_active", "nickname", "power", "seated", "user_id"]
        assert seats["FRANCE"]["user_id"] == db_service.get_user_by_telegram_id(anna).id
        assert seats["FRANCE"]["seated"] is True
        assert isinstance(seats["FRANCE"]["user_id"], int)
        assert isinstance(_listed(client, game_id)["players"][0]["user_id"], int)


class TestAnnouncements:
    def test_an_anonymous_join_is_announced_by_power_alone(self, client):
        (anna, _), (cleo, cleo_nick) = _telegram_user(client, "Anna"), _telegram_user(client, "Cleo")
        game_id = str(client.post(
            "/games/create", json={"map_name": "standard", "anonymous": True, **_as(anna)}, headers=_BOT,
        ).json()["game_id"])
        assert client.post(f"/games/{game_id}/join", json=_as(anna, power="FRANCE")).status_code == 200
        with OutboxProbe() as probe:
            assert client.post(f"/games/{game_id}/join", json=_as(cleo, power="ITALY")).status_code == 200
        sent = probe.by_recipient()
        assert f"A new player has joined game {game_id} as ITALY." in sent[anna]
        assert sent[cleo] == [
            f"You have joined game {game_id} as ITALY. "
            f"It is anonymous: the other players know you only as your power."
        ]
        assert not any(cleo_nick in m for m in probe.messages())

    def test_a_public_join_names_the_player(self, client):
        game_id, anna, *_ = _game(client, anonymous=False)
        cleo, cleo_nick = _telegram_user(client, "Cleo")
        with OutboxProbe() as probe:
            # Lower case in, upper case out -- the announcement and the response.
            r = client.post(f"/games/{game_id}/join", json=_as(cleo, power="italy"))
            assert (r.status_code, r.json()["power"]) == (200, "ITALY")
        sent = probe.by_recipient()
        assert f"{cleo_nick} has joined game {game_id} as ITALY." in sent[anna]
        # The joiner hears it once, as "You have joined", not again as "Cleo has joined".
        assert sent[cleo] == [f"You have joined game {game_id} as ITALY."]

    def test_my_orders_name_my_power_in_upper_case(self, client):
        game_id, anna, *_ = _game(client, anonymous=False)
        r = client.get(f"/games/{game_id}/orders/france", params={"telegram_id": anna, "bot_secret": BOT_SECRET})
        assert (r.status_code, r.json()) == (200, {"power": "FRANCE", "orders": []})

    @pytest.mark.parametrize("anonymous", [True, False])
    def test_a_wait_flag_names_the_power_and_in_a_public_game_the_player(self, client, anonymous):
        game_id, anna, bert, bert_nick = _game(client, anonymous=anonymous)
        label = _label(anonymous, "GERMANY", bert_nick)
        with OutboxProbe() as probe:
            r = client.post(f"/games/{game_id}/wait", json=_as(bert, power="GERMANY", waiting=True))
        assert r.status_code == 200, r.text
        assert probe.by_recipient()[anna] == [f"{label} asks game {game_id} to wait before the turn is processed."]

    @pytest.mark.parametrize("anonymous", [True, False])
    def test_a_quit_names_the_power_and_in_a_public_game_the_player(self, client, anonymous):
        game_id, anna, bert, bert_nick = _game(client, anonymous=anonymous)
        label = _label(anonymous, "GERMANY", bert_nick)
        with OutboxProbe() as probe:
            assert client.post(f"/games/{game_id}/quit", json=_as(bert)).status_code == 200
        assert f"{label} has left game {game_id}." in probe.by_recipient()[anna]


class TestRelayedMessages:
    @pytest.mark.parametrize("anonymous", [True, False])
    def test_a_private_message_names_the_sender_by_power(self, client, anonymous):
        game_id, anna, bert, bert_nick = _game(client, anonymous=anonymous)
        label = _label(anonymous, "GERMANY", bert_nick)
        with OutboxProbe() as probe:
            r = client.post(f"/games/{game_id}/message", json=_as(bert, recipient_power="FRANCE", text="Ally?"))
        assert r.status_code == 200, r.text
        assert probe.by_recipient()[anna] == [f"New private message in game {game_id} from {label}: Ally?"]

    @pytest.mark.parametrize("anonymous", [True, False])
    def test_a_broadcast_names_the_sender_by_power(self, client, anonymous):
        game_id, anna, bert, bert_nick = _game(client, anonymous=anonymous)
        label = _label(anonymous, "GERMANY", bert_nick)
        with OutboxProbe() as probe:
            r = client.post(f"/games/{game_id}/broadcast", json=_as(bert, text="Peace"))
        assert r.status_code == 200, r.text
        assert probe.by_recipient()[anna] == [f"Broadcast in game {game_id} from {label}: Peace"]

    def test_the_message_log_of_an_anonymous_game_names_powers_only(self, client):
        game_id, anna, bert, _ = _game(client, anonymous=True)
        client.post(f"/games/{game_id}/message", json=_as(bert, recipient_power="FRANCE", text="Ally?"))
        logged = client.get(f"/games/{game_id}/messages", params=_as(anna)).json()["messages"]
        assert [(m["sender_user_id"], m["sender_power"], m["sender_name"], m["text"]) for m in logged] == [
            (None, "GERMANY", None, "Ally?"),
        ]

    def test_the_message_log_of_a_public_game_names_the_sender(self, client):
        game_id, anna, bert, bert_nick = _game(client, anonymous=False)
        client.post(f"/games/{game_id}/message", json=_as(bert, recipient_power="FRANCE", text="Ally?"))
        logged = client.get(f"/games/{game_id}/messages", params=_as(anna)).json()["messages"]
        assert [(m["sender_power"], m["sender_name"], m["text"]) for m in logged] == [("GERMANY", bert_nick, "Ally?")]
        assert isinstance(logged[0]["sender_user_id"], int)
