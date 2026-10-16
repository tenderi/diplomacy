"""Track BL: a game takes no moves before it starts (BL1), and a power that has
left the game stays out of it (BL2).

BL1: a game whose table was not full accepted orders, draw votes and a
concession -- a power conceding in the lobby was dead once the table filled.
BL2: a conceded power could still send press, vote on a draw (announced as a
vote), concede again (re-announced to everyone) and quit and rejoin its dead
seat; and a game with one power left went on with nobody to play against.
"""
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api.shared import db_service, game_service
from server.api.routes.auth import _create_access_token
from server.game_service import GameService
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies

BOT_SECRET = "test_bot_secret_for_tests"
BOT = {"X-Bot-Secret": BOT_SECRET}

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

_tg_seq = 0


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _telegram_user(client: TestClient) -> str:
    # Numeric, like a real Telegram id: ``notify_players`` skips non-numeric ids.
    global _tg_seq
    _tg_seq += 1
    tg = str(int(time.time() * 1000) % 10**9 * 10 + _tg_seq % 10)
    r = client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": tg})
    assert r.status_code == 200, r.text
    return tg


def _as(tg: str, **extra: object) -> dict[str, object]:
    return {"telegram_id": tg, "bot_secret": BOT_SECRET, **extra}


def _game(client: TestClient, powers: list[str], **create: object) -> tuple[str, dict[str, str]]:
    """A game with a telegram user seated in each of ``powers``."""
    game_id = str(client.post("/games/create", json={"map_name": "standard", **create}, headers=BOT).json()["game_id"])
    seated = {}
    for power in powers:
        tg = _telegram_user(client)
        r = client.post(f"/games/{game_id}/join", json=_as(tg, power=power))
        assert r.status_code == 200, r.text
        seated[power] = tg
    return game_id, seated


def _not_started(game_id: str) -> str:
    return (
        f"Game {game_id} hasn't started: 6 powers are unseated "
        f"(Austria, England, Germany, Italy, Russia, Turkey): seat players or mark them as dummies."
    )


class TestNothingHappensBeforeTheGameStarts:
    def test_orders_are_refused(self, client: TestClient) -> None:
        game_id, seats = _game(client, ["FRANCE"])
        r = client.post("/games/set_orders", json=_as(seats["FRANCE"], game_id=game_id, power="FRANCE", orders=["A PAR - BUR"]))
        assert r.status_code == 409
        assert r.json()["detail"] == _not_started(game_id)
        assert r.headers["X-Error-Code"] == "seats_unfilled"
        assert game_service.pending_orders_view(game_id) == {}

    def test_a_draw_vote_is_refused(self, client: TestClient) -> None:
        game_id, seats = _game(client, ["FRANCE"])
        r = client.post(f"/games/{game_id}/draw_vote", json=_as(seats["FRANCE"], power="FRANCE", vote=True))
        assert r.status_code == 409
        assert r.json()["detail"] == _not_started(game_id)
        assert game_service.get_draw_votes(game_id)["votes"] == []

    def test_a_concession_is_refused_and_the_board_is_untouched(self, client: TestClient) -> None:
        game_id, seats = _game(client, ["FRANCE"])
        r = client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE"))
        assert r.status_code == 409
        assert r.json()["detail"] == _not_started(game_id)
        france = game_service.view(game_id)["units_by_power"]["FRANCE"]
        assert sorted(u["location"] for u in france) == ["BRE", "MAR", "PAR"]

    def test_a_full_table_takes_orders(self, client: TestClient) -> None:
        game_id, seats = _game(client, ["FRANCE"])
        fill_with_dummies(game_id)
        r = client.post("/games/set_orders", json=_as(seats["FRANCE"], game_id=game_id, power="FRANCE", orders=["A PAR - BUR"]))
        assert r.status_code == 200, r.text
        assert game_service.pending_orders_view(game_id) == {"FRANCE": ["A PAR - BUR"]}

    def test_a_started_game_with_a_reopened_seat_still_takes_orders(self, client: TestClient) -> None:
        """Reopening a dummy seat after a turn holds up processing, not orders."""
        game_id, seats = _game(client, ["FRANCE"])
        fill_with_dummies(game_id)
        assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
        game_service.set_dummy(game_id, "AUSTRIA", False)
        r = client.post("/games/set_orders", json=_as(seats["FRANCE"], game_id=game_id, power="FRANCE", orders=["A PAR H"]))
        assert r.status_code == 200, r.text

    def test_orders_stored_before_the_guard_survive_it(self, client: TestClient) -> None:
        """A game one seat short that already holds orders (live game 2 when this
        shipped): new orders wait, the stored ones stay readable and are
        adjudicated once the last seat is filled."""
        powers = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "TURKEY"]
        game_id, seats = _game(client, powers)
        game_service.submit_orders(game_id, "FRANCE", ["A PAR - BUR"])  # stored before the guard existed
        r = client.post("/games/set_orders", json=_as(seats["FRANCE"], game_id=game_id, power="FRANCE", orders=["A PAR H"]))
        assert r.status_code == 409
        assert r.json()["detail"] == (
            f"Game {game_id} hasn't started: 1 power is unseated (Russia): seat players or mark them as dummies."
        )
        stored = client.get(f"/games/{game_id}/orders/FRANCE", params={"telegram_id": seats["FRANCE"], "bot_secret": BOT_SECRET})
        assert stored.json()["orders"] == ["A PAR - BUR"]
        assert client.get(f"/games/{game_id}/state").json()["phase"] == "S1901M"
        russia = _telegram_user(client)
        assert client.post(f"/games/{game_id}/join", json=_as(russia, power="RUSSIA")).status_code == 200
        assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
        france = game_service.view(game_id)["units_by_power"]["FRANCE"]
        assert sorted(u["location"] for u in france) == ["BRE", "BUR", "MAR"]


class TestAConcededPowerIsOut:
    def _conceded(self, client: TestClient) -> tuple[str, dict[str, str]]:
        game_id, seats = _game(client, ["FRANCE", "GERMANY", "ITALY"])
        fill_with_dummies(game_id)
        r = client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE"))
        assert r.status_code == 200, r.text
        assert r.json()["eliminated"] is True
        return game_id, seats

    def test_a_second_concession_is_refused_and_not_announced(self, client: TestClient) -> None:
        game_id, seats = self._conceded(client)
        with patch("server.api.routes.games.notify_players") as players:
            r = client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE"))
        assert r.status_code == 409
        assert r.json()["detail"] == "FRANCE has already conceded"
        players.assert_not_called()

    def test_it_cannot_send_press(self, client: TestClient) -> None:
        game_id, seats = self._conceded(client)
        refused = f"FRANCE has been eliminated from game {game_id}; it can no longer send messages."
        r = client.post(f"/games/{game_id}/message", json=_as(seats["FRANCE"], recipient_power="GERMANY", text="hi"))
        assert (r.status_code, r.json()["detail"]) == (409, refused)
        r = client.post(f"/games/{game_id}/broadcast", json=_as(seats["FRANCE"], text="hi"))
        assert (r.status_code, r.json()["detail"]) == (409, refused)
        # The others still talk.
        r = client.post(f"/games/{game_id}/message", json=_as(seats["GERMANY"], recipient_power="ITALY", text="hi"))
        assert r.status_code == 200, r.text

    def test_it_cannot_post_to_the_group_as_its_power(self, client: TestClient) -> None:
        game_id, seats = self._conceded(client)
        with patch("server.api.routes.channels.db_service.get_game_channel_info", return_value={"channel_id": "-100"}):
            r = client.post(
                f"/games/{game_id}/channel/broadcast", headers=BOT,
                json={"telegram_id": seats["FRANCE"], "message": "hi", "power": "FRANCE"},
            )
        assert r.status_code == 409
        assert r.json()["detail"] == f"FRANCE has been eliminated from game {game_id}; it can no longer send messages."

    @pytest.mark.parametrize("claimed", [None, "ENGLAND", "GERMANY"])
    def test_a_web_user_cannot_post_to_the_group_by_naming_another_power(
        self, client: TestClient, claimed: str | None,
    ) -> None:
        """The route trusted the body's ``power``: a conceded web user sent
        ``null`` (a "PUBLIC BROADCAST") or another power's name and was posted."""
        game_id, seats = self._conceded(client)
        user = db_service.get_user_by_telegram_id(seats["FRANCE"])
        bearer = {"Authorization": f"Bearer {_create_access_token(int(user.id))}"}
        with (
            patch("server.api.routes.channels.db_service.get_game_channel_info", return_value={"channel_id": "-100"}),
            patch("server.api.routes.channels.db_service.enqueue_bot_notification") as queued,
        ):
            r = client.post(
                f"/games/{game_id}/channel/broadcast", headers=bearer,
                json={"telegram_id": seats["GERMANY"], "message": "hi", "power": claimed},
            )
        if claimed is None:
            assert (r.status_code, r.json()["detail"]) == (
                409, f"FRANCE has been eliminated from game {game_id}; it can no longer send messages.",
            )
        else:
            assert (r.status_code, r.json()["detail"]) == (403, f"You do not hold {claimed} in game {game_id}")
        queued.assert_not_called()

    def test_a_web_user_posts_as_their_own_power(self, client: TestClient) -> None:
        game_id, seats = self._conceded(client)
        user = db_service.get_user_by_telegram_id(seats["GERMANY"])
        bearer = {"Authorization": f"Bearer {_create_access_token(int(user.id))}"}
        with (
            patch("server.api.routes.channels.db_service.get_game_channel_info", return_value={"channel_id": "-100"}),
            patch("server.api.routes.channels.db_service.enqueue_bot_notification", return_value=1) as queued,
        ):
            r = client.post(
                f"/games/{game_id}/channel/broadcast", headers=bearer,
                json={"telegram_id": seats["ITALY"], "message": "hi"},
            )
        assert r.status_code == 200, r.text
        assert queued.call_args.args[1] == "📢 *GERMANY* → All Powers\n\nhi"

    @pytest.mark.parametrize("claimed", [None, "GERMANY"])
    def test_the_bot_cannot_post_for_a_conceded_player(self, client: TestClient, claimed: str | None) -> None:
        game_id, seats = self._conceded(client)
        with (
            patch("server.api.routes.channels.db_service.get_game_channel_info", return_value={"channel_id": "-100"}),
            patch("server.api.routes.channels.db_service.enqueue_bot_notification") as queued,
        ):
            r = client.post(
                f"/games/{game_id}/channel/broadcast", headers=BOT,
                json={"telegram_id": seats["FRANCE"], "message": "hi", "power": claimed},
            )
        expected = (
            (409, f"FRANCE has been eliminated from game {game_id}; it can no longer send messages.")
            if claimed is None else (403, f"You do not hold GERMANY in game {game_id}")
        )
        assert (r.status_code, r.json()["detail"]) == expected
        queued.assert_not_called()

    def test_it_cannot_vote_on_a_draw(self, client: TestClient) -> None:
        game_id, seats = self._conceded(client)
        with patch("server.api.shared.notify_players") as players:
            r = client.post(f"/games/{game_id}/draw_vote", json=_as(seats["FRANCE"], power="FRANCE", vote=True))
        assert r.status_code == 409
        assert r.json()["detail"] == f"FRANCE has been eliminated from game {game_id}; it cannot vote on a draw"
        players.assert_not_called()
        assert game_service.get_draw_votes(game_id)["votes"] == []

    def test_its_seat_cannot_be_taken_back(self, client: TestClient) -> None:
        game_id, seats = self._conceded(client)
        assert client.post(f"/games/{game_id}/quit", json=_as(seats["FRANCE"])).status_code == 200
        refused = f"FRANCE has been eliminated from game {game_id}; its seat cannot be taken."
        r = client.post(f"/games/{game_id}/join", json=_as(seats["FRANCE"], power="FRANCE"))
        assert (r.status_code, r.json()["detail"]) == (409, refused)
        newcomer = _telegram_user(client)
        r = client.post(f"/games/{game_id}/replace", json=_as(newcomer, power="FRANCE"))
        assert (r.status_code, r.json()["detail"]) == (409, refused)
        seat = db_service.get_player_by_game_id_and_power(game_id=game_id, power="FRANCE")
        assert seat.user_id is None

    def test_a_random_join_skips_a_dead_seat(self, client: TestClient) -> None:
        game_id, _ = _game(client, [], random_powers=True)
        held = {}
        for tg in [_telegram_user(client) for _ in range(7)]:
            r = client.post(f"/games/{game_id}/join", json=_as(tg))
            assert r.status_code == 200, r.text
            held[r.json()["power"]] = tg
        assert client.post(f"/games/{game_id}/concede", json=_as(held["FRANCE"], power="FRANCE")).status_code == 200
        assert client.post(f"/games/{game_id}/quit", json=_as(held["FRANCE"])).status_code == 200
        r = client.post(f"/games/{game_id}/join", json=_as(_telegram_user(client)))
        assert r.status_code == 409
        assert r.json()["detail"] == f"Game {game_id} is full: every power is taken."


class TestTheLastPowerStandingWins:
    def test_the_last_concession_ends_the_game(self, client: TestClient) -> None:
        game_id, seats = _game(client, ["FRANCE", "GERMANY"])
        fill_with_dummies(game_id)
        # The five dummies leave the board too (a dummy is a power still playing).
        for power in ("AUSTRIA", "ENGLAND", "ITALY", "RUSSIA", "TURKEY"):
            assert game_service.concede(game_id, power)["game_status"] == "ACTIVE"
        warm = client.get(f"/users/{seats['GERMANY']}/games", headers=BOT)
        assert warm.status_code == 200, warm.text

        with patch("server.api.shared.notify_players") as players, patch("server.api.shared.post_to_game_group") as group:
            r = client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE"))
        assert r.status_code == 200, r.text
        assert r.json() == {
            "status": "ok", "power": "FRANCE", "game_status": "COMPLETED", "eliminated": True,
            "winners": ["GERMANY"], "auto_processed": False,
        }
        state = client.get(f"/games/{game_id}/state").json()
        assert (state["status"], state["winners"]) == ("COMPLETED", ["GERMANY"])
        assert game_service.meta(game_id)["status"] == "completed"

        ended = f"FRANCE has conceded, and game {game_id} has ended"
        (numeric, text), kwargs = players.call_args
        assert text == f"{ended}: GERMANY is the last power standing and wins."
        assert kwargs["own"](["GERMANY"]) == f"{ended}: you are the last power standing and win."
        assert kwargs["own"](["FRANCE"]) is None
        assert kwargs["exclude_telegram_id"] == seats["FRANCE"]
        group.assert_called_once_with(game_id, f"🏆 Game {game_id} has ended\n{ended}: GERMANY is the last power standing and wins.")
        # The winner's cached game list shows the ended game.
        listed = client.get(f"/users/{seats['GERMANY']}/games", headers=BOT).json()
        assert [g["status"] for g in listed["games"] if str(g["game_id"]) == game_id] == ["completed"]

    def test_two_powers_left_play_on(self, client: TestClient) -> None:
        game_id, seats = _game(client, ["FRANCE", "GERMANY"])
        fill_with_dummies(game_id)
        for power in ("AUSTRIA", "ENGLAND", "ITALY", "RUSSIA"):
            game_service.concede(game_id, power)
        r = client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE"))
        assert r.status_code == 200, r.text
        assert (r.json()["game_status"], r.json()["winners"]) == ("ACTIVE", [])

    def test_two_last_concessions_at_once_announce_one_end(self, client: TestClient) -> None:
        """ITALY and FRANCE concede together and leave GERMANY. FRANCE's request
        ended the game; ITALY's, finding it ended, used to say "the remaining
        powers play on", try to auto-process and report the game ACTIVE."""
        game_id, seats = _game(client, ["FRANCE", "GERMANY", "ITALY"])
        fill_with_dummies(game_id)
        for power in ("AUSTRIA", "ENGLAND", "RUSSIA", "TURKEY"):
            game_service.concede(game_id, power)
        original = GameService._end_if_last_standing
        raced: list[dict[str, object]] = []
        started: list[bool] = []

        def france_concedes_first(service: GameService, gid: str) -> object:
            if not started:  # ITALY has left the board; FRANCE's whole request lands now
                started.append(True)
                raced.append(service.concede(gid, "FRANCE"))
            return original(service, gid)

        with (
            patch.object(GameService, "_end_if_last_standing", autospec=True, side_effect=france_concedes_first),
            patch("server.api.shared.notify_players") as players,
            patch("server.api.routes.games.notify_players") as play_on,
            patch("server.api.shared.maybe_auto_process") as auto,
        ):
            r = client.post(f"/games/{game_id}/concede", json=_as(seats["ITALY"], power="ITALY"))
        assert r.status_code == 200, r.text
        assert r.json() == {
            "status": "ok", "power": "ITALY", "game_status": "COMPLETED", "eliminated": True,
            "winners": ["GERMANY"], "auto_processed": False,
        }
        assert raced[0]["ended_game"] is True
        play_on.assert_not_called()
        players.assert_not_called()  # the end is FRANCE's request's to announce
        auto.assert_not_called()
