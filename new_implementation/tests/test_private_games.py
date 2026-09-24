"""W8: private games -- joining needs the game's password; the creator is exempt.

The password is stored as a bcrypt hash and never leaves the API: views and
listings carry only ``private``. Wrong guesses are rate-limited per user and
game, like login attempts.
"""
import json

import pytest
from fastapi.testclient import TestClient

from server.api import app
from tests.conftest import _get_db_url
from tests.test_quit_and_replace import BOT_SECRET, _as, _register_and_login, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

ADMIN = {"X-Admin-Token": "changeme"}  # conftest's default admin token
BOT = {"X-Bot-Secret": BOT_SECRET}
PASSWORD = "open sesame"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _private_game(client: TestClient) -> tuple[str, dict]:
    creator = _register_and_login(client, "priv")
    resp = client.post("/games/create", json={"map_name": "standard", "join_password": PASSWORD}, headers=creator)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["game_id"]), creator


def test_private_is_visible_and_the_hash_never_is(client: TestClient) -> None:
    game_id, _creator = _private_game(client)
    state = client.get(f"/games/{game_id}/state")
    listing = client.get("/games")
    export = client.get(f"/games/{game_id}/export", headers=ADMIN)
    assert state.json()["private"] is True
    assert next(g for g in listing.json()["games"] if str(g["id"]) == game_id)["private"] is True
    for body in (state.text, listing.text, json.dumps(export.json())):
        assert "$2b$" not in body and PASSWORD not in body


def test_joining_needs_the_password(client: TestClient) -> None:
    game_id, _creator = _private_game(client)
    tg = _telegram_user(client, "joiner")
    missing = client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
    assert missing.status_code == 403 and "is private" in missing.json()["detail"]
    wrong = client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE", join_password="nope"))
    assert wrong.status_code == 403 and "Wrong join password" in wrong.json()["detail"]
    right = client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE", join_password=PASSWORD))
    assert right.status_code == 200, right.text


def test_the_creator_joins_without_it(client: TestClient) -> None:
    game_id, creator = _private_game(client)
    assert client.post(f"/games/{game_id}/join", json={"power": "ENGLAND"}, headers=creator).status_code == 200


def test_guessing_is_rate_limited(client: TestClient) -> None:
    game_id, _creator = _private_game(client)
    tg = _telegram_user(client, "guesser")
    for _ in range(5):
        assert client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE", join_password="x")).status_code == 403
    # Locked out -- even the right password waits for the window to pass.
    locked = client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE", join_password=PASSWORD))
    assert locked.status_code == 429


def test_taking_over_a_vacated_seat_needs_it_too(client: TestClient) -> None:
    game_id, _creator = _private_game(client)
    a, b = _telegram_user(client, "leaver"), _telegram_user(client, "taker")
    assert client.post(f"/games/{game_id}/join", json=_as(a, power="FRANCE", join_password=PASSWORD)).status_code == 200
    assert client.post(f"/games/{game_id}/quit", json=_as(a)).status_code == 200
    assert client.post(f"/games/{game_id}/replace", json=_as(b, power="FRANCE")).status_code == 403
    ok = client.post(f"/games/{game_id}/replace", json=_as(b, power="FRANCE", join_password=PASSWORD))
    assert ok.status_code == 200, ok.text


class TestChangingThePassword:
    def test_the_creator_can_open_the_game_again(self, client: TestClient) -> None:
        game_id, creator = _private_game(client)
        resp = client.post(f"/games/{game_id}/join_password", json={"join_password": None}, headers=creator)
        assert resp.status_code == 200 and resp.json()["private"] is False
        assert client.get(f"/games/{game_id}/state").json()["private"] is False
        tg = _telegram_user(client, "free")
        assert client.post(f"/games/{game_id}/join", json=_as(tg, power="ITALY")).status_code == 200

    def test_an_open_game_can_be_made_private(self, client: TestClient) -> None:
        creator = _register_and_login(client, "priv")
        game_id = str(client.post("/games/create", json={"map_name": "standard"}, headers=creator).json()["game_id"])
        client.post(f"/games/{game_id}/join_password", json={"join_password": "later!"}, headers=creator)
        tg = _telegram_user(client, "late")
        assert client.post(f"/games/{game_id}/join", json=_as(tg, power="ITALY")).status_code == 403

    def test_only_the_creator_or_an_admin(self, client: TestClient) -> None:
        game_id, _creator = _private_game(client)
        stranger = _register_and_login(client, "stranger")
        assert client.post(f"/games/{game_id}/join_password", json={"join_password": None}, headers=stranger).status_code == 403
        assert client.post(f"/games/{game_id}/join_password", json={"join_password": None}, headers=ADMIN).status_code == 200

    @pytest.mark.parametrize("bad", ["abc", "x" * 65])
    def test_length_is_checked(self, client: TestClient, bad: str) -> None:
        creator = _register_and_login(client, "priv")
        resp = client.post("/games/create", json={"map_name": "standard", "join_password": bad}, headers=creator)
        assert resp.status_code == 400
