"""Group games on the server: hidden from the public list, joined only through
the bot, their group settings guarded, and announcements queued for the group.
"""
import time

import pytest
from fastapi.testclient import TestClient

from server.api import ADMIN_TOKEN, app
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies
from tests.reliability_helpers import OutboxProbe
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

BOT = {"X-Bot-Secret": BOT_SECRET}
GROUP = "-1001234567"
# Tests reuse one group id: an admin may move its link from the last test's game.
ADMIN_LINK = {**BOT, "X-Admin-Token": ADMIN_TOKEN}


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
    assert client.post(f"/games/{game_id}/channel/link", json={"channel_id": GROUP}, headers=ADMIN_LINK).status_code == 200
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
        group = f"-100{time.time_ns() % 10**10}"
        assert client.post(f"/games/{game_id}/channel/link", json={"channel_id": group}, headers=BOT).status_code == 200
        assert client.get(f"/games/{game_id}/channel", headers=creator).json()["channel_id"] == group
        assert client.post(f"/games/{game_id}/channel/settings", json={"auto_post_maps": False}, headers=BOT).status_code == 200
        assert client.delete(f"/games/{game_id}/channel/unlink", headers=BOT).status_code == 200

    def test_the_web_page_shows_a_player_the_group_and_lets_them_unlink_it(self, client: TestClient) -> None:
        """BB2b: the game page reads the group's title and the bot's username, and unlinks."""
        player = _web_user(client, "webunlinker")
        game_id = str(client.post("/games/create", json={"map_name": "standard"}, headers=player).json()["game_id"])
        client.post(f"/games/{game_id}/join", json={"power": "ITALY"}, headers=player)
        group = f"-100{time.time_ns() % 10**10}"
        link = {"channel_id": group, "channel_name": "Friday Diplomacy"}
        assert client.post(f"/games/{game_id}/channel/link", json=link, headers=BOT).status_code == 200
        info = client.get(f"/games/{game_id}/channel", headers=player).json()
        assert (info["linked"], info["channel_name"], info["bot_username"]) == (True, "Friday Diplomacy", "IronChancellorBot")

        stranger = _web_user(client, "notinthegame")
        assert client.delete(f"/games/{game_id}/channel/unlink", headers=stranger).status_code == 403
        assert client.get(f"/games/{game_id}/channel", headers=player).json()["linked"] is True

        assert client.delete(f"/games/{game_id}/channel/unlink", headers=player).status_code == 200
        after = client.get(f"/games/{game_id}/channel", headers=player).json()
        assert (after["linked"], after["bot_username"]) == (False, "IronChancellorBot")
        assert client.get("/channels/" + group + "/game", headers=BOT).json() == {"linked": False}


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
    fill_with_dummies(game_id)
    with OutboxProbe() as probe:
        assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    text_posts = [r for r in probe.rows() if str(r["telegram_id"]) == GROUP and r["kind"] == "channel_text"]
    assert text_posts[0]["payload"]["dm_start"] == f"orders_{game_id}"



class TestAGroupHasOneGame:
    """#158: a group belongs to at most one game, and a command typed in the
    group finds it through ``GET /channels/{id}/game``. Only a player of the
    game that has the group may move it to another game."""

    @staticmethod
    def _fresh_group() -> str:
        return f"-100{time.time_ns() % 10**10}"

    def _game(self, client: TestClient, *players: str) -> str:
        """A game created by a fresh Telegram user, with ``players`` seated."""
        creator = _telegram_user(client, "grouponegame")
        game_id = str(client.post("/games/create", json=_as(creator, map_name="standard"), headers=BOT).json()["game_id"])
        for tg, power in zip(players, ("FRANCE", "GERMANY", "ITALY")):
            assert client.post(f"/games/{game_id}/join", json=_as(tg, power=power)).status_code == 200
        return game_id

    def _link(self, client: TestClient, game_id: str, group: str, **extra: object) -> object:
        return client.post(f"/games/{game_id}/channel/link", json={"channel_id": group, **extra}, headers=BOT)

    def _linked_group(self, client: TestClient, game_id: str) -> str:
        group = self._fresh_group()
        assert self._link(client, game_id, group, channel_name="Friday").json()["replaced_game_id"] is None
        return group

    def test_a_player_of_the_groups_game_moves_the_link_and_is_told_which_game_it_replaced(self, client: TestClient) -> None:
        anna = _telegram_user(client, "anna")
        first, second = self._game(client, anna), self._game(client, anna)
        group = self._linked_group(client, first)
        resp = self._link(client, second, group, channel_name="Friday", telegram_id=anna)
        assert resp.status_code == 200, resp.text
        assert resp.json()["replaced_game_id"] == first
        assert client.get(f"/games/{first}/channel", headers=BOT).json()["linked"] is False
        assert client.get(f"/channels/{group}/game", headers=BOT).json() == {
            "linked": True, "game_id": second, "channel_name": "Friday",
        }

    @pytest.mark.parametrize("who", ["stranger", "nobody"])
    def test_the_bot_cannot_move_a_link_for_someone_who_does_not_play_the_groups_game(self, client: TestClient, who: str) -> None:
        """The /linkgroup and /newgame paths: the caller plays the new game only
        (or the bot names nobody)."""
        anna, bert = _telegram_user(client, "anna"), _telegram_user(client, "bert")
        theirs, mine = self._game(client, anna), self._game(client, bert)
        group = self._linked_group(client, theirs)
        extra = {"telegram_id": bert} if who == "stranger" else {}
        resp = self._link(client, mine, group, **extra)
        assert resp.status_code == 409
        assert resp.json()["detail"] == (
            f"That Telegram group already belongs to game {theirs}. "
            f"Only a player of game {theirs} can move the group to another game."
        )
        assert client.get(f"/channels/{group}/game", headers=BOT).json()["game_id"] == theirs
        public = [str(g["id"]) for g in client.get("/games").json()["games"]]
        assert theirs not in public

    def test_relinking_the_same_game_replaces_nothing(self, client: TestClient) -> None:
        game_id = self._game(client)
        group = self._linked_group(client, game_id)
        resp = self._link(client, game_id, group)
        assert resp.status_code == 200, resp.text
        assert resp.json()["replaced_game_id"] is None
        assert client.get(f"/channels/{group}/game", headers=BOT).json()["game_id"] == game_id

    def test_a_group_without_a_game(self, client: TestClient) -> None:
        assert client.get(f"/channels/{self._fresh_group()}/game", headers=BOT).json() == {"linked": False}

    def test_only_the_bot_may_ask_which_game_a_group_plays(self, client: TestClient) -> None:
        web = _web_user(client, "groupsnoop")
        assert client.get(f"/channels/{GROUP}/game").status_code == 401
        assert client.get(f"/channels/{GROUP}/game", headers=web).status_code == 401

    def _web_game(self, client: TestClient, web: dict) -> str:
        game_id = str(client.post("/games/create", json={"map_name": "standard"}, headers=web).json()["game_id"])
        assert client.post(f"/games/{game_id}/join", json={"power": "ITALY"}, headers=web).status_code == 200
        return game_id

    @pytest.mark.parametrize("taken", [False, True])
    def test_a_web_login_cannot_link_any_group_even_a_players(self, client: TestClient, taken: bool) -> None:
        """BB9: any chat id would do, so a player who knows a group's id could
        squat it with their game. Only the bot, from inside the group, links."""
        web = _web_user(client, "groupsquatter")
        mine = self._web_game(client, web)
        group = self._linked_group(client, self._game(client)) if taken else self._fresh_group()
        resp = client.post(f"/games/{mine}/channel/link", json={"channel_id": group}, headers=web)
        assert resp.status_code == 403
        assert resp.json()["detail"] == (
            "A game is linked to a Telegram group from inside the group: add the bot and send /linkgroup there."
        )
        assert client.get(f"/games/{mine}/channel", headers=web).json()["linked"] is False

    # -- /newgame: POST /games/create with the group's channel_id (BB9) --------

    def _create_in_group(self, client: TestClient, tg: str, group: str) -> object:
        return client.post(
            "/games/create",
            json=_as(tg, map_name="standard", channel_id=group, channel_name="Friday"),
            headers=BOT,
        )

    @staticmethod
    def _games_created_by(tg: str) -> list[str]:
        from persistence.database import GameModel
        from server.api.shared import db_service

        user_id = db_service.get_user_by_telegram_id(tg).id
        with db_service.session_factory() as session:
            return [str(g.game_id) for g in session.query(GameModel).filter_by(created_by_user_id=user_id)]

    def test_a_game_created_for_a_group_is_linked_to_it(self, client: TestClient) -> None:
        anna, group = _telegram_user(client, "anna"), self._fresh_group()
        resp = self._create_in_group(client, anna, group)
        assert resp.status_code == 200, resp.text
        game_id = str(resp.json()["game_id"])
        assert resp.json()["replaced_game_id"] is None
        assert client.get(f"/channels/{group}/game", headers=BOT).json() == {
            "linked": True, "game_id": game_id, "channel_name": "Friday",
        }

    def test_a_game_the_group_cannot_have_is_not_created_at_all(self, client: TestClient) -> None:
        """A refused link used to leave the new game behind, unlinked and in the public list."""
        anna, bert = _telegram_user(client, "anna"), _telegram_user(client, "bert")
        theirs = self._game(client, anna)
        group = self._linked_group(client, theirs)
        before = [str(g["id"]) for g in client.get("/games").json()["games"]]
        resp = self._create_in_group(client, bert, group)
        assert resp.status_code == 409
        assert resp.json()["detail"].startswith(f"That Telegram group already belongs to game {theirs}.")
        assert self._games_created_by(bert) == []
        assert [str(g["id"]) for g in client.get("/games").json()["games"]] == before
        assert client.get(f"/channels/{group}/game", headers=BOT).json()["game_id"] == theirs

    def test_a_player_of_the_groups_game_creates_its_replacement(self, client: TestClient) -> None:
        anna = _telegram_user(client, "anna")
        theirs = self._game(client, anna)
        group = self._linked_group(client, theirs)
        resp = self._create_in_group(client, anna, group)
        assert resp.status_code == 200, resp.text
        assert resp.json()["replaced_game_id"] == theirs
        assert client.get(f"/channels/{group}/game", headers=BOT).json()["game_id"] == str(resp.json()["game_id"])

    def test_only_the_bot_creates_a_game_for_a_group(self, client: TestClient) -> None:
        web, group = _web_user(client, "groupcreator"), self._fresh_group()
        resp = client.post("/games/create", json={"map_name": "standard", "channel_id": group}, headers=web)
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Only the bot creates a game for a Telegram group."
        assert client.get(f"/channels/{group}/game", headers=BOT).json() == {"linked": False}

    def test_the_database_refuses_two_games_in_one_group(self) -> None:
        from sqlalchemy.exc import IntegrityError

        from persistence.database import GameModel
        from server.api.shared import db_service

        group = self._fresh_group()
        with db_service.session_factory() as session:
            for n in range(2):
                session.add(GameModel(game_id=f"dup{time.time_ns()}{n}", map_name="standard", channel_id=group))
            with pytest.raises(IntegrityError, match="uq_games_channel_id"):
                session.commit()
