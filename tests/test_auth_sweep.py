"""Track T: reads and writes that took "someone" for "this person".

- ``GET /users/{telegram_id}/games`` was anonymous: which games any Telegram
  user plays, and as which power, for anyone who could guess the id. Now the
  bot secret, or a Bearer user reading their *own* linked id. The check is a
  dependency, because the route is wrapped in ``@cached_response`` and a check
  in the body would be skipped on every cache hit.
- ``POST /games/{id}/deadline`` accepted any Bearer user for any game if they
  simply omitted ``telegram_id``. Now every caller must hold a power there.
- ``POST /users/register`` / ``GET /users/{telegram_id}`` -- an anonymous,
  unbounded in-memory session store nothing ever read -- are gone.
"""
import datetime
import time

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api.shared import db_service
from tests.conftest import _get_db_url

BOT = {"X-Bot-Secret": "test_bot_secret_for_tests"}

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


@pytest.fixture
def client():
    return TestClient(app)


def _bearer_user(client, tag, telegram_id=None):
    reg = client.post("/auth/register", json={"email": f"sweep_{tag}_{int(time.time() * 1000000)}@example.com", "password": "testpass123"})
    assert reg.status_code == 200, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    if telegram_id is not None:
        user_id = int(client.get("/auth/me", headers=headers).json()["id"])
        db_service.set_user_telegram_id(user_id, telegram_id)
    return headers


class TestUserGamesRead:
    def test_anonymous_is_401_even_after_the_bot_warmed_the_cache(self, client):
        tg = str(int(time.time() * 1000) % 10**9)
        _bearer_user(client, "owner", telegram_id=tg)
        assert client.get(f"/users/{tg}/games", headers=BOT).status_code == 200  # populates the cache
        assert client.get(f"/users/{tg}/games").status_code == 401
        assert client.get(f"/users/{tg}/games", headers={"X-Bot-Secret": "wrong"}).status_code == 401

    def test_bearer_user_may_read_own_id_but_not_another(self, client):
        tg = str(int(time.time() * 1000) % 10**9 + 1)
        mine = _bearer_user(client, "self", telegram_id=tg)
        other = _bearer_user(client, "other", telegram_id=str(int(tg) + 7))
        assert client.get(f"/users/{tg}/games", headers=mine).status_code == 200
        assert client.get(f"/users/{tg}/games", headers=other).status_code == 401


class TestDeadlineNeedsAPlayer:
    def test_bearer_non_member_is_403_member_is_200(self, client):
        creator = _bearer_user(client, "creator")
        game_id = client.post("/games/create", json={"map_name": "standard"}, headers=creator).json()["game_id"]
        future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).isoformat()
        stranger = _bearer_user(client, "stranger")
        assert client.post(f"/games/{game_id}/deadline", json={"deadline": future}, headers=stranger).status_code == 403
        assert client.get(f"/games/{game_id}/deadline").json()["deadline"] is None
        assert client.post(f"/games/{game_id}/join", json={"power": "ENGLAND"}, headers=stranger).status_code == 200
        assert client.post(f"/games/{game_id}/deadline", json={"deadline": future}, headers=stranger).status_code == 200
        assert client.get(f"/games/{game_id}/deadline").json()["deadline"] is not None

    def test_bot_secret_with_a_foreign_telegram_id_still_needs_membership(self, client):
        creator = _bearer_user(client, "creator2")
        game_id = client.post("/games/create", json={"map_name": "standard"}, headers=creator).json()["game_id"]
        tg = str(int(time.time() * 1000) % 10**9 + 3)
        _bearer_user(client, "outsider", telegram_id=tg)
        future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).isoformat()
        r = client.post(f"/games/{game_id}/deadline", json={"deadline": future, "telegram_id": tg}, headers=BOT)
        assert r.status_code == 403, r.text


class TestSessionRoutesAreGone:
    def test_register_and_session_read_are_404(self, client):
        assert client.post("/users/register", json={"telegram_id": "x", "game_id": "1", "power": "FRANCE"}).status_code == 404
        # /users/{telegram_id} used to be the session read; nothing routes there now.
        assert client.get("/users/whoever").status_code == 404
