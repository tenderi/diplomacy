"""Route-authorization guards a coverage sweep found unhit (BU1).

Each test pins the exact status and detail of a refusal, and the state it must
leave alone, so a regression that lets the wrong user act fails here:

- a Telegram-group game is joined through the bot, except by its creator;
- only a player (or an admin) switches a game's auto-processing;
- only the creator (or an admin) changes its dummy powers;
- only an *access* token authenticates a Bearer request (not a refresh or a
  password-reset token), and only while its user is active.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from server.api import ADMIN_TOKEN, app
from server.api.shared import db_service, game_service
from tests.conftest import _get_db_url
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

BOT = {"X-Bot-Secret": BOT_SECRET}
ADMIN = {"X-Admin-Token": ADMIN_TOKEN}
GROUP = "-1009876543"
GROUP_JOIN_REFUSED = (403, "This game belongs to a Telegram group. Join it from the group, through the Diplomacy bot.")
NOT_A_PLAYER = (403, "You are not a player in this game.")
NOT_THE_CREATOR = (403, "Only the game's creator can change its dummy powers.")
BAD_TOKEN = (401, "Invalid or expired token")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _registered(client: TestClient, prefix: str) -> tuple[int, dict[str, str], str]:
    """A web user: their id, a Bearer header and their refresh token."""
    email = f"{prefix}_{time.time_ns()}@example.com"
    reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert reg.status_code == 200, reg.text
    body = reg.json()
    return int(body["user"]["id"]), {"Authorization": f"Bearer {body['access_token']}"}, body["refresh_token"]


def _game(client: TestClient, bearer: dict[str, str]) -> str:
    resp = client.post("/games/create", json={"map_name": "standard"}, headers=bearer)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["game_id"])


def _detail(resp) -> tuple[int, str]:
    return resp.status_code, resp.json()["detail"]


class TestGroupGameJoin:
    def _group_game(self, client: TestClient) -> tuple[str, dict[str, str]]:
        """A game a web user created, then linked to a Telegram group."""
        _, creator, _ = _registered(client, "bu1_groupcreator")
        game_id = _game(client, creator)
        link = client.post(f"/games/{game_id}/channel/link", json={"channel_id": GROUP}, headers={**BOT, **ADMIN})
        assert link.status_code == 200, link.text
        return game_id, creator

    def test_the_creator_joins_directly_from_the_web(self, client: TestClient) -> None:
        game_id, creator = self._group_game(client)
        resp = client.post(f"/games/{game_id}/join", json={"power": "FRANCE"}, headers=creator)
        assert resp.status_code == 200, resp.text
        assert db_service.get_player_by_game_id_and_power(game_id=game_id, power="FRANCE").user_id is not None

    def test_anyone_else_without_the_bot_secret_is_refused_and_not_seated(self, client: TestClient) -> None:
        game_id, _ = self._group_game(client)
        _, stranger, _ = _registered(client, "bu1_groupstranger")
        resp = client.post(f"/games/{game_id}/join", json={"power": "FRANCE"}, headers=stranger)
        assert _detail(resp) == GROUP_JOIN_REFUSED
        assert db_service.get_player_by_game_id_and_power(game_id=game_id, power="FRANCE") is None


class TestAutoProcess:
    def test_a_non_member_is_refused_and_the_setting_is_unchanged(self, client: TestClient) -> None:
        _, creator, _ = _registered(client, "bu1_auto")
        game_id = _game(client, creator)
        outsider = _telegram_user(client, "bu1_outsider")
        resp = client.post(f"/games/{game_id}/auto_process", json=_as(outsider, enabled=True))
        assert _detail(resp) == NOT_A_PLAYER
        assert game_service.meta(game_id)["auto_process"] is False

    def test_the_creator_who_holds_no_seat_is_not_a_member_either(self, client: TestClient) -> None:
        _, creator, _ = _registered(client, "bu1_auto_creator")
        game_id = _game(client, creator)
        resp = client.post(f"/games/{game_id}/auto_process", json={"enabled": True}, headers=creator)
        assert _detail(resp) == NOT_A_PLAYER
        assert game_service.meta(game_id)["auto_process"] is False

    def test_an_unknown_game_is_404(self, client: TestClient) -> None:
        member = _telegram_user(client, "bu1_member")
        resp = client.post("/games/999999999/auto_process", json=_as(member, enabled=True))
        assert _detail(resp) == (404, "Game not found")

    def test_a_seated_player_may_switch_it(self, client: TestClient) -> None:
        _, creator, _ = _registered(client, "bu1_auto_ok")
        game_id = _game(client, creator)
        player = _telegram_user(client, "bu1_player")
        assert client.post(f"/games/{game_id}/join", json=_as(player, power="FRANCE")).status_code == 200
        resp = client.post(f"/games/{game_id}/auto_process", json=_as(player, enabled=True))
        assert resp.status_code == 200, resp.text
        assert game_service.meta(game_id)["auto_process"] is True


class TestDummyPowers:
    def test_a_seated_player_who_is_not_the_creator_is_refused(self, client: TestClient) -> None:
        _, creator, _ = _registered(client, "bu1_dummy")
        game_id = _game(client, creator)
        member = _telegram_user(client, "bu1_dummy_member")
        assert client.post(f"/games/{game_id}/join", json=_as(member, power="FRANCE")).status_code == 200
        resp = client.post(f"/games/{game_id}/dummies", json=_as(member, power="ITALY"))
        assert _detail(resp) == NOT_THE_CREATOR
        assert game_service.meta(game_id)["dummy_powers"] == []


class TestBearerTokenTypes:
    def test_a_refresh_token_is_not_an_access_token(self, client: TestClient) -> None:
        _, bearer, refresh = _registered(client, "bu1_refresh")
        assert client.get("/auth/me", headers=bearer).status_code == 200
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {refresh}"})
        assert _detail(resp) == BAD_TOKEN

    def test_a_password_reset_token_is_not_an_access_token(self, client: TestClient) -> None:
        user_id, _, _ = _registered(client, "bu1_reset")
        reset = db_service.create_password_reset_token(user_id)
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {reset}"})
        assert _detail(resp) == BAD_TOKEN

    def test_a_refresh_token_cannot_act_for_a_power(self, client: TestClient) -> None:
        _, bearer, refresh = _registered(client, "bu1_refresh_power")
        game_id = _game(client, bearer)
        assert client.post(f"/games/{game_id}/join", json={"power": "FRANCE"}, headers=bearer).status_code == 200
        resp = client.post(
            "/games/set_orders",
            json={"game_id": game_id, "power": "FRANCE", "orders": ["A PAR H"]},
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert _detail(resp) == (401, "Not authenticated")


class TestInactiveUserOnAPowerGatedRoute:
    def test_an_inactive_users_access_token_cannot_order_for_their_power(self, client: TestClient) -> None:
        user_id, bearer, _ = _registered(client, "bu1_inactive")
        game_id = _game(client, bearer)
        assert client.post(f"/games/{game_id}/join", json={"power": "FRANCE"}, headers=bearer).status_code == 200
        db_service.set_user_active(user_id, False)
        resp = client.post(
            "/games/set_orders",
            json={"game_id": game_id, "power": "FRANCE", "orders": ["A PAR H"]},
            headers=bearer,
        )
        assert _detail(resp) == (401, "Not authenticated")
        assert game_service.pending_orders_view(game_id) == {}
