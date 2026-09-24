"""Group games on the server: hidden from the public list, joined only through
the bot, their group settings guarded, and announcements queued for the group.
"""
import time

import pytest
from fastapi.testclient import TestClient

from server.api import app
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

BOT = {"X-Bot-Secret": BOT_SECRET}
GROUP = "-1001234567"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _web_user(client: TestClient, name: str) -> dict:
    email = f"{name}_{time.time_ns()}@example.com"
    token = client.post("/auth/register", json={"email": email, "password": "testpass123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _group_game(client: TestClient) -> tuple[str, str]:
    creator = _telegram_user(client, "groupcreator")
    game_id = str(client.post("/games/create", json=_as(creator, map_name="standard"), headers=BOT).json()["game_id"])
    assert client.post(f"/games/{game_id}/channel/link", json={"channel_id": GROUP}, headers=BOT).status_code == 200
    return game_id, creator


def test_the_public_list_hides_group_games_and_the_bot_sees_them_with_their_group(client: TestClient) -> None:
    game_id, _ = _group_game(client)
    public = [str(g["id"]) for g in client.get("/games").json()["games"]]
    for_bot = {str(g["id"]): g for g in client.get("/games", headers=BOT).json()["games"]}
    assert game_id not in public
    assert for_bot[game_id]["channel_id"] == GROUP
    assert all("channel_id" not in g for g in client.get("/games").json()["games"])


def test_a_web_user_cannot_join_a_group_game_directly_but_the_bot_can_seat_them(client: TestClient) -> None:
    game_id, _ = _group_game(client)
    web = _web_user(client, "outsider")
    resp = client.post(f"/games/{game_id}/join", json={"power": "FRANCE"}, headers=web)
    assert resp.status_code == 403 and "Telegram group" in resp.json()["detail"]
    tg = _telegram_user(client, "member")
    assert client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE")).status_code == 200


class TestGroupSettingsAreGuarded:
    def test_strangers_cannot_unlink_or_post(self, client: TestClient) -> None:
        game_id, _ = _group_game(client)
        stranger = _web_user(client, "stranger")
        assert client.delete(f"/games/{game_id}/channel/unlink").status_code == 403
        assert client.delete(f"/games/{game_id}/channel/unlink", headers=stranger).status_code == 403
        assert client.post(f"/games/{game_id}/channel/map", headers=stranger).status_code == 403
        assert client.get(f"/games/{game_id}/channel").status_code == 403
        assert client.post(f"/games/{game_id}/channel/link", json={"channel_id": "-1"}, headers=stranger).status_code == 403

    def test_a_seated_web_player_and_the_bot_may(self, client: TestClient) -> None:
        creator = _web_user(client, "webplayer")
        game_id = str(client.post("/games/create", json={"map_name": "standard"}, headers=creator).json()["game_id"])
        client.post(f"/games/{game_id}/join", json={"power": "ITALY"}, headers=creator)
        assert client.post(f"/games/{game_id}/channel/link", json={"channel_id": GROUP}, headers=creator).status_code == 200
        assert client.get(f"/games/{game_id}/channel", headers=creator).json()["channel_id"] == GROUP
        assert client.post(f"/games/{game_id}/channel/settings", json={"auto_post_maps": False}, headers=BOT).status_code == 200
        assert client.delete(f"/games/{game_id}/channel/unlink", headers=BOT).status_code == 200


def test_the_group_hears_about_a_deadline_change(client: TestClient) -> None:
    game_id, creator = _group_game(client)
    client.post(f"/games/{game_id}/join", json=_as(creator, power="FRANCE"))
    with OutboxProbe() as probe:
        resp = client.post(f"/games/{game_id}/deadline", json=_as(creator, deadline=None))
    assert resp.status_code == 200, resp.text
    group_posts = [r for r in probe.rows() if str(r["telegram_id"]) == GROUP and r["kind"] == "channel_text"]
    assert group_posts and "deadline" in group_posts[0]["message"].lower()


def test_a_processed_turn_tells_the_group_with_a_private_orders_link(client: TestClient) -> None:
    game_id, _ = _group_game(client)
    with OutboxProbe() as probe:
        assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    text_posts = [r for r in probe.rows() if str(r["telegram_id"]) == GROUP and r["kind"] == "channel_text"]
    assert text_posts[0]["payload"]["dm_start"] == f"orders_{game_id}"
