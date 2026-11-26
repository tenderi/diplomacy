"""DV4c: whoever creates a game is seated in it, exactly as if they had joined
straight after creating it -- the bot's /newgame (also in a group) and the web.

The create route runs the join route's own code, so the power assignment, the
DMs, the group post and the cache invalidation are the join's. A join that
fails leaves the game created and says why in ``seat``.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from server._api_module import app
from tests.bot_client import BotTestClient
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_anonymous_games import _BOT, _as, _telegram_user

pytestmark = [
    pytest.mark.integration,
    pytest.mark.database,
    pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured"),
]


@pytest.fixture
def client() -> BotTestClient:
    return BotTestClient(app)


def _create(client: TestClient, tg: str, **settings: object) -> dict:
    r = client.post("/games/create", json={"map_name": "standard", **settings, **_as(tg)}, headers=_BOT)
    assert r.status_code == 200, r.text
    return r.json()


def _seats(client: TestClient, game_id: str) -> dict[str, bool]:
    return {p["power"]: p["seated"] for p in client.get(f"/games/{game_id}/players").json() if p["seated"]}


class TestTheBot:
    def test_newgame_with_a_power_seats_the_creator_and_dms_them(self, client: BotTestClient) -> None:
        tg, _nick = _telegram_user(client, "Cre")
        with OutboxProbe() as probe:
            created = _create(client, tg, power="france")
        game_id = str(created["game_id"])
        assert created["seat"] == {"status": "ok", "power": "FRANCE", "reason": None}
        assert _seats(client, game_id) == {"FRANCE": True}
        assert probe.by_recipient()[tg] == [f"You have joined game {game_id} as FRANCE."]

    def test_the_creators_game_list_shows_the_seat_at_once(self, client: BotTestClient) -> None:
        tg, _nick = _telegram_user(client, "Lst")
        assert client.get(f"/users/{tg}/games", headers=_BOT).json()["games"] == []
        game_id = str(_create(client, tg, power="ITALY")["game_id"])
        games = client.get(f"/users/{tg}/games", headers=_BOT).json()["games"]
        assert [(str(g["game_id"]), g["power"]) for g in games] == [(game_id, "ITALY")]

    def test_a_random_powers_game_deals_the_creator_a_power(self, client: BotTestClient) -> None:
        tg, _nick = _telegram_user(client, "Rnd")
        created = _create(client, tg, random_powers=True, dummy_powers=["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA"])
        assert created["seat"] == {"status": "ok", "power": "TURKEY", "reason": None}

    def test_without_a_power_the_game_is_created_and_the_reason_given(self, client: BotTestClient) -> None:
        tg, _nick = _telegram_user(client, "Nop")
        with OutboxProbe() as probe:
            created = _create(client, tg)
        game_id = str(created["game_id"])
        assert created["seat"] == {"status": "not_seated", "power": None, "reason": "Choose a power to join as."}
        assert _seats(client, game_id) == {}
        assert client.get(f"/games/{game_id}/state").status_code == 200
        assert tg not in probe.recipients()

    def test_a_private_game_seats_its_creator_without_the_password(self, client: BotTestClient) -> None:
        tg, _nick = _telegram_user(client, "Pwd")
        created = _create(client, tg, power="ENGLAND", join_password="secret-pw")
        assert created["seat"] == {"status": "ok", "power": "ENGLAND", "reason": None}

    def test_newgame_in_a_group_seats_the_creator_and_tells_the_group(self, client: BotTestClient) -> None:
        tg, nick = _telegram_user(client, "Grp")
        group = f"-100{time.time_ns() % 10**12}"
        with OutboxProbe() as probe:
            created = _create(
                client, tg, random_powers=True, channel_id=group, channel_name="Test group", auto_process=True,
            )
        game_id = str(created["game_id"])
        power = created["seat"]["power"]
        assert created["seat"] == {"status": "ok", "power": power, "reason": None}
        assert created["replaced_game_id"] is None
        assert _seats(client, game_id) == {power: True}
        assert probe.by_recipient()[group] == [f"{nick} has joined game {game_id} as {power}."]
        assert probe.by_recipient()[tg] == [f"You have joined game {game_id} as {power}."]

    def test_an_anonymous_group_game_keeps_the_creators_power_from_the_group(self, client: BotTestClient) -> None:
        """The group watched the creator type /newgame: a join post naming the
        dealt power would unmask them. Only the creator's own DM names it."""
        tg, _nick = _telegram_user(client, "Mask")
        group = f"-100{time.time_ns() % 10**12}"
        with OutboxProbe() as probe:
            created = _create(
                client, tg, random_powers=True, anonymous=True, channel_id=group, channel_name="Test group",
                auto_process=True,
            )
        game_id = str(created["game_id"])
        power = created["seat"]["power"]
        assert created["seat"] == {"status": "ok", "power": power, "reason": None}
        assert _seats(client, game_id) == {power: True}
        assert [m for m in probe.messages() if " joined game " in m] == [
            f"You have joined game {game_id} as {power}. "
            "It is anonymous: the other players know you only as your power."
        ]
        assert group not in probe.recipients()

    def test_an_anonymous_game_says_so_in_the_creators_dm(self, client: BotTestClient) -> None:
        tg, _nick = _telegram_user(client, "Ano")
        with OutboxProbe() as probe:
            game_id = str(_create(client, tg, power="RUSSIA", anonymous=True)["game_id"])
        assert probe.by_recipient()[tg] == [
            f"You have joined game {game_id} as RUSSIA. "
            "It is anonymous: the other players know you only as your power."
        ]


class TestTheWeb:
    def test_creating_a_game_seats_the_logged_in_user(self) -> None:
        client = TestClient(app)
        reg = client.post(
            "/auth/register", json={"email": f"dv4c_{time.time_ns()}@example.com", "password": "testpass123"}
        )
        assert reg.status_code == 200, reg.text
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        r = client.post("/games/create", json={"map_name": "standard", "power": "GERMANY"}, headers=headers)
        assert r.status_code == 200, r.text
        game_id = str(r.json()["game_id"])
        assert r.json()["seat"] == {"status": "ok", "power": "GERMANY", "reason": None}
        mine = client.get("/users/me/games", headers=headers).json()["games"]
        assert [(str(g["game_id"]), g["power"]) for g in mine] == [(game_id, "GERMANY")]


class TestASeatingThatFails:
    def test_a_database_error_leaves_the_game_and_reports_it(
        self, client: BotTestClient, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from sqlalchemy.exc import OperationalError

        from server.api.routes import games as games_routes

        def down(**_kw: object) -> None:
            raise OperationalError("SELECT", {}, Exception("connection lost"))

        tg, _nick = _telegram_user(client, "Err")
        monkeypatch.setattr(games_routes.db_service, "get_player_by_game_id_and_user_id", down)
        created = _create(client, tg, power="FRANCE")
        monkeypatch.undo()
        assert created["seat"] == {"status": "not_seated", "power": None, "reason": games_routes.SEAT_FAILED}
        assert client.get(f"/games/{created['game_id']}/state").status_code == 200
        assert _seats(client, str(created["game_id"])) == {}


class TestNobodyToSeat:
    def test_a_bare_bot_secret_creates_an_ownerless_unseated_game(self, client: BotTestClient) -> None:
        r = client.post("/games/create", json={"map_name": "standard"}, headers=_BOT)
        assert r.status_code == 200, r.text
        assert r.json()["seat"] is None
        assert _seats(client, str(r.json()["game_id"])) == {}


class TestAPowerNoJoinCouldTake:
    """Refused before anything is created: the request itself is wrong."""

    @pytest.mark.parametrize(("settings", "detail"), [
        ({"power": "SPAIN"}, "Invalid power name: SPAIN"),
        ({"power": "FRANCE", "random_powers": True},
         "Powers are assigned at random in this game: create it without choosing one."),
        ({"power": "france", "dummy_powers": ["FRANCE"]},
         "FRANCE is left to civil disorder in this game: choose another power."),
    ])
    def test_is_refused_and_creates_nothing(self, client: BotTestClient, settings: dict, detail: str) -> None:
        tg, _nick = _telegram_user(client, "Bad")
        before = {g["game_id"] for g in client.get("/games").json()["games"]}
        r = client.post("/games/create", json={"map_name": "standard", **settings, **_as(tg)}, headers=_BOT)
        assert r.status_code == 400
        assert r.json()["detail"] == detail
        assert {g["game_id"] for g in client.get("/games").json()["games"]} == before

    def test_a_power_with_nobody_to_seat_is_refused(self, client: BotTestClient) -> None:
        r = client.post("/games/create", json={"map_name": "standard", "power": "FRANCE"}, headers=_BOT)
        assert r.status_code == 400
        assert r.json()["detail"] == "A power is taken by a player: send who is creating the game."
