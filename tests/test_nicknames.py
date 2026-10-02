"""The system holds no real names: a player is known by their power and, if they
chose one, a nickname. Nothing is taken from a Telegram profile."""
from __future__ import annotations

import time
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api.shared import db_service
from server.nickname import display_name, normalize_nickname, sender_label
from server.telegram_bot.games import nickname as nickname_command
from tests.conftest import _get_db_url
from tests.test_bot_commands import _command, _http_error, _run

BOT_SECRET = "test_bot_secret_for_tests"
needs_db = pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _nick(prefix: str = "Nick") -> str:
    return f"{prefix} {uuid.uuid4().hex[:8]}"  # unique: the test DB outlives a run


def _telegram(client: TestClient) -> str:
    tg = str(int(time.time() * 1_000_000) % 10**12)
    assert client.post("/users/persistent_register", json={"telegram_id": tg, "bot_secret": BOT_SECRET}).status_code == 200
    return tg


@pytest.mark.unit
class TestRules:
    @pytest.mark.parametrize(("raw", "expected"), [
        (None, None), ("", None), ("   ", None),
        ("  Talleyrand  ", "Talleyrand"), ("Iron   Duke", "Iron Duke"), ("a_b-c.d", "a_b-c.d"), ("Ääkkönen", "Ääkkönen"),
    ])
    def test_accepted(self, raw: str | None, expected: str | None) -> None:
        assert normalize_nickname(raw) == expected

    @pytest.mark.parametrize("raw", ["x", "y" * 25, "no*stars", "[link]", "back`tick", "new\nline!"])
    def test_refused(self, raw: str) -> None:
        with pytest.raises(ValueError, match="2-24 characters"):
            normalize_nickname(raw)

    def test_display_falls_back_to_a_neutral_label(self) -> None:
        class U:
            nickname = None
        assert display_name(U()) == "A player"
        assert display_name(None, "The FRANCE player") == "The FRANCE player"

    def test_messages_are_from_the_power(self) -> None:
        class U:
            nickname = "Talleyrand"
        assert sender_label("FRANCE", None) == "FRANCE"
        assert sender_label("FRANCE", U()) == "FRANCE (Talleyrand)"


@needs_db
@pytest.mark.unit
class TestStoring:
    def test_a_name_sent_with_registration_is_not_stored(self, client: TestClient) -> None:
        """An old bot (or anything else) sending the Telegram name must not get it stored."""
        tg = str(uuid.uuid4().int % 10**12)
        resp = client.post("/users/persistent_register",
                           json={"telegram_id": tg, "bot_secret": BOT_SECRET, "full_name": "Ada Lovelace", "username": "ada"})
        assert resp.status_code == 200 and resp.json()["nickname"] is None
        assert db_service.get_user_by_telegram_id(tg).nickname is None

    def test_the_web_registers_with_a_nickname_and_never_derives_one(self, client: TestClient) -> None:
        nick = _nick()
        with_nick = client.post("/auth/register", json={"email": f"{uuid.uuid4().hex}@example.com", "password": "pass12345", "nickname": f"  {nick} "})
        assert with_nick.status_code == 200 and with_nick.json()["user"]["nickname"] == nick
        email = f"ada.lovelace.{uuid.uuid4().hex[:6]}@example.com"
        without = client.post("/auth/register", json={"email": email, "password": "pass12345"})
        assert without.json()["user"]["nickname"] is None  # not "ada.lovelace..." from the email

    def test_nicknames_are_unique_ignoring_case(self, client: TestClient) -> None:
        nick = _nick()
        assert client.post("/auth/register", json={"email": f"{uuid.uuid4().hex}@example.com", "password": "pass12345", "nickname": nick}).status_code == 200
        taken = client.post("/auth/register", json={"email": f"{uuid.uuid4().hex}@example.com", "password": "pass12345", "nickname": nick.upper()})
        assert (taken.status_code, taken.json()["detail"]) == (409, "That nickname is taken")

    def test_the_web_sets_and_clears_its_nickname(self, client: TestClient) -> None:
        reg = client.post("/auth/register", json={"email": f"{uuid.uuid4().hex}@example.com", "password": "pass12345"})
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        nick = _nick()
        assert client.patch("/auth/me", json={"nickname": nick}, headers=headers).json()["nickname"] == nick
        assert client.patch("/auth/me", json={"nickname": "x"}, headers=headers).status_code == 422
        assert client.patch("/auth/me", json={"nickname": ""}, headers=headers).json()["nickname"] is None

    def test_the_bot_sets_a_nickname_for_its_caller_only(self, client: TestClient) -> None:
        tg, other = _telegram(client), _telegram(client)
        nick = _nick()
        assert client.post("/users/nickname", json={"telegram_id": tg, "nickname": nick}).status_code == 401
        assert client.post("/users/nickname", json={"telegram_id": tg, "bot_secret": BOT_SECRET, "nickname": nick}).status_code == 200
        assert db_service.get_user_by_telegram_id(tg).nickname == nick
        clash = client.post("/users/nickname", json={"telegram_id": other, "bot_secret": BOT_SECRET, "nickname": nick.lower()})
        assert clash.status_code == 409
        unknown = client.post("/users/nickname", json={"telegram_id": "no-such-user", "bot_secret": BOT_SECRET, "nickname": _nick()})
        assert unknown.status_code == 404

    def test_the_players_list_shows_the_nickname_and_nothing_else(self, client: TestClient) -> None:
        tg = _telegram(client)
        nick = _nick()
        client.post("/users/nickname", json={"telegram_id": tg, "bot_secret": BOT_SECRET, "nickname": nick})
        game_id = client.post("/games/create", json={"map_name": "standard", "telegram_id": tg, "bot_secret": BOT_SECRET},
                              headers={"X-Bot-Secret": BOT_SECRET}).json()["game_id"]
        assert client.post(f"/games/{game_id}/join", json={"telegram_id": tg, "bot_secret": BOT_SECRET, "power": "FRANCE"}).status_code == 200
        france = next(p for p in client.get(f"/games/{game_id}/players").json() if p["power"] == "FRANCE")
        assert france["nickname"] == nick and "full_name" not in france


@pytest.mark.unit
class TestBotCommand:
    def test_without_an_argument_it_shows_the_nickname(self) -> None:
        with patch("server.telegram_bot.games.api_post", return_value={"nickname": "Talleyrand"}):
            assert _run(nickname_command, *_command(text="/nickname")).startswith("Your nickname is Talleyrand.")

    def test_it_sets_one(self) -> None:
        with patch("server.telegram_bot.games.api_post", return_value={"status": "ok"}) as post:
            reply = _run(nickname_command, *_command(text="/nickname  Iron   Duke "))
        post.assert_called_with("/users/nickname", {"telegram_id": "555", "nickname": "Iron   Duke"})
        assert reply == "✅ Your nickname is now Iron Duke."

    def test_a_dash_clears_it(self) -> None:
        with patch("server.telegram_bot.games.api_post", return_value={"status": "ok"}) as post:
            reply = _run(nickname_command, *_command(text="/nickname -"))
        post.assert_called_with("/users/nickname", {"telegram_id": "555", "nickname": None})
        assert reply == "✅ Nickname cleared."

    @pytest.mark.parametrize(("status", "reply"), [
        (409, "❌ That nickname is taken."),
        (422, "❌ A nickname is 2-24 characters: letters, digits, spaces, '.', '_' or '-'."),
    ])
    def test_a_refusal_says_why(self, status: int, reply: str) -> None:
        def post(path: str, payload: dict) -> dict:
            if path == "/users/nickname":
                raise _http_error(status, "x")
            return {}
        with patch("server.telegram_bot.games.api_post", side_effect=post):
            assert _run(nickname_command, *_command(text="/nickname Taken Name")) == reply

    def test_registration_sends_no_profile_name(self) -> None:
        with patch("server.telegram_bot.games.api_post", return_value={"nickname": None}) as post:
            _run(nickname_command, *_command(text="/nickname"))
        assert all(set(call.args[1]) <= {"telegram_id", "nickname"} for call in post.call_args_list)
