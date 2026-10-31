"""BZ1 and BZ4: game endings that a vote or a turn did not cause.

BZ1: a draw whose quorum is completed by a concession or by a seat made a dummy
-- both leave the quorum -- never ended the game; only a vote checked it, so
``draw_vote_status`` showed ``quorum_reached`` on an ACTIVE game until the next
processed phase wiped the votes. BZ4: when every human-held power had conceded
and only dummies were left, the game stayed ACTIVE forever. A seat its player
quit is not a dummy (it can be taken again) and keeps the game going.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from engine.serialization import state_to_dict
from engine.types import GameState, Location, PhaseType, Season, Unit, UnitKind
from server.api import app
from server.api.shared import db_service, game_service
from server.response_cache import clear_response_cache
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies
from tests.test_seat_guards import BOT, _as, _game

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

ADMIN = {"X-Admin-Token": "changeme"}  # conftest's default admin token
SHARERS = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "RUSSIA", "TURKEY"]  # all but ITALY, on the board


@pytest.fixture
def client() -> TestClient:
    clear_response_cache()
    return TestClient(app)


def _listed_status(client: TestClient, tg: str, game_id: str) -> list[str]:
    games = client.get(f"/users/{tg}/games", headers=BOT).json()["games"]
    return [g["status"] for g in games if str(g["game_id"]) == game_id]


def _three_humans_two_voting(client: TestClient) -> tuple[str, dict[str, str]]:
    """FRANCE, GERMANY and ITALY seated, the rest dummies; FRANCE and GERMANY
    have voted for a draw, ITALY has not."""
    game_id, seats = _game(client, ["FRANCE", "GERMANY", "ITALY"])
    fill_with_dummies(game_id)
    for power in ("FRANCE", "GERMANY"):
        r = client.post(f"/games/{game_id}/draw_vote", json=_as(seats[power], power=power, vote=True))
        assert r.status_code == 200, r.text
        assert r.json()["quorum_reached"] is False
    return game_id, seats


def _status(client: TestClient, game_id: str) -> dict[str, Any]:
    state = client.get(f"/games/{game_id}/state").json()
    return {"status": state["status"], "winners": sorted(state.get("winners") or [])}


class TestAConcessionCompletesTheDraw:
    def test_the_game_ends_as_the_draw_and_is_announced_as_one(self, client: TestClient) -> None:
        game_id, seats = _three_humans_two_voting(client)
        assert _listed_status(client, seats["FRANCE"], game_id) == ["active"]  # warm the cache
        db_service.update_game_deadline(int(game_id), datetime.now(timezone.utc) + timedelta(hours=6))
        with (
            patch("server.api.shared.notify_players") as players,
            patch("server.api.shared.post_to_game_group") as group,
            patch("server.api.routes.games.notify_players") as play_on,
            patch("server.api.shared._notify_daide_drawn") as daide,
        ):
            r = client.post(f"/games/{game_id}/concede", json=_as(seats["ITALY"], power="ITALY"))
        assert r.status_code == 200, r.text
        assert r.json() == {
            "status": "ok", "power": "ITALY", "game_status": "COMPLETED", "eliminated": True,
            "winners": SHARERS, "how": "draw", "auto_processed": False,
        }
        assert _status(client, game_id) == {"status": "COMPLETED", "winners": SHARERS}
        assert game_service.ending(game_id) == {"winners": SHARERS, "how": "draw"}
        text = (
            f"ITALY has conceded, and game {game_id} has ended in a draw shared by "
            "AUSTRIA, ENGLAND, FRANCE, GERMANY, RUSSIA and TURKEY."
        )
        group.assert_called_once_with(game_id, f"🤝 Draw - Game {game_id}\n{text}")
        assert players.call_args.args[1] == text
        assert players.call_args.kwargs["exclude_telegram_id"] == seats["ITALY"]
        play_on.assert_not_called()  # no "the remaining powers play on"
        daide.assert_called_once_with(game_id)
        assert _listed_status(client, seats["FRANCE"], game_id) == ["completed"]
        assert db_service.get_game_by_game_id(game_id).deadline is None

    def test_a_vote_withdrawn_meanwhile_is_decided_again(self, client: TestClient) -> None:
        """GERMANY withdraws after ITALY's concession was written and before its
        quorum check: the check reads the votes on the locked row, so the draw
        is decided on the new votes and refused."""
        game_id, _ = _three_humans_two_voting(client)
        repo = game_service._repo
        real_end = repo.end_game_if
        calls: list[int] = []

        def germany_withdraws_first(gid: str, *args: Any, **kwargs: Any) -> bool:
            if not calls:
                repo.modify_draw_votes(gid, lambda v: {p: x for p, x in v.items() if p != "GERMANY"})
            calls.append(1)
            return real_end(gid, *args, **kwargs)

        with patch.object(repo, "end_game_if", side_effect=germany_withdraws_first):
            result = game_service.concede(game_id, "ITALY")
        assert result["game_status"] == "ACTIVE"
        assert result["ended_game"] is False
        assert len(calls) == 2  # the last-standing check, then the draw's
        assert game_service.load(game_id).state.status.value == "ACTIVE"
        assert repo.get_draw_votes(game_id) == {"FRANCE": "yes"}


class TestADummyCompletesTheDraw:
    def test_making_the_last_holdout_a_dummy_ends_the_game_as_the_draw(self, client: TestClient) -> None:
        game_id, seats = _three_humans_two_voting(client)
        r = client.post(f"/games/{int(game_id)}/quit", json=_as(seats["ITALY"], power="ITALY"))
        assert r.status_code == 200, r.text
        status = client.get(f"/games/{game_id}/draw_vote_status").json()
        assert (status["missing"], status["quorum_reached"]) == (["ITALY"], False)
        assert _listed_status(client, seats["FRANCE"], game_id) == ["active"]  # warm the cache

        with (
            patch("server.api.shared.notify_players") as players,
            patch("server.api.shared.post_to_game_group") as group,
            patch("server.api.routes.games.notify_players") as plain,
            patch("server.api.shared._notify_daide_drawn") as daide,
        ):
            r = client.post(f"/games/{game_id}/dummies", json={"power": "ITALY", "dummy": True}, headers=ADMIN)
        assert r.status_code == 200, r.text
        everyone = sorted([*SHARERS, "ITALY"])
        assert r.json() == {
            "status": "ok", "dummy_powers": ["AUSTRIA", "ENGLAND", "ITALY", "RUSSIA", "TURKEY"],
            "ended": "draw", "winners": everyone,
        }
        assert _status(client, game_id) == {"status": "COMPLETED", "winners": everyone}
        text = (
            f"ITALY is now played by civil disorder, and game {game_id} has ended in a draw shared by "
            "AUSTRIA, ENGLAND, FRANCE, GERMANY, ITALY, RUSSIA and TURKEY."
        )
        group.assert_called_once_with(game_id, f"🤝 Draw - Game {game_id}\n{text}")
        assert players.call_args.args[1] == text
        plain.assert_not_called()
        daide.assert_called_once_with(game_id)
        assert _listed_status(client, seats["FRANCE"], game_id) == ["completed"]


def test_a_voted_draw_refreshes_each_players_cached_game_list(client: TestClient) -> None:
    game_id, seats = _game(client, ["FRANCE", "GERMANY"])
    fill_with_dummies(game_id)
    assert client.post(f"/games/{game_id}/draw_vote", json=_as(seats["FRANCE"], power="FRANCE", vote=True)).status_code == 200
    assert _listed_status(client, seats["FRANCE"], game_id) == ["active"]  # warm the cache
    r = client.post(f"/games/{game_id}/draw_vote", json=_as(seats["GERMANY"], power="GERMANY", vote=True))
    assert r.json()["quorum_reached"] is True
    assert _listed_status(client, seats["FRANCE"], game_id) == ["completed"]


class TestOnlyDummiesLeft:
    def test_the_last_human_conceding_ends_the_game_with_no_winner(self, client: TestClient) -> None:
        game_id, seats = _game(client, ["FRANCE", "GERMANY"])
        fill_with_dummies(game_id)
        assert game_service.concede(game_id, "FRANCE")["game_status"] == "ACTIVE"
        assert _listed_status(client, seats["GERMANY"], game_id) == ["active"]  # warm the cache
        with (
            patch("server.api.shared.notify_players") as players,
            patch("server.api.shared.post_to_game_group") as group,
            patch("server.api.shared._notify_daide_drawn") as daide,
        ):
            r = client.post(f"/games/{game_id}/concede", json=_as(seats["GERMANY"], power="GERMANY"))
        assert r.status_code == 200, r.text
        assert r.json() == {
            "status": "ok", "power": "GERMANY", "game_status": "COMPLETED", "eliminated": True,
            "winners": [], "how": "only_dummies", "auto_processed": False,
        }
        assert _status(client, game_id) == {"status": "COMPLETED", "winners": []}
        text = f"GERMANY has conceded, and game {game_id} has ended: only civil-disorder powers are left, so nobody wins."
        group.assert_called_once_with(game_id, f"🏆 Game {game_id} has ended\n{text}")
        assert players.call_args.args[1] == text
        daide.assert_called_once_with(game_id)
        assert _listed_status(client, seats["GERMANY"], game_id) == ["completed"]

    def test_a_vacated_seat_keeps_the_game_going(self, client: TestClient) -> None:
        game_id, seats = _game(client, ["FRANCE", "GERMANY"])
        fill_with_dummies(game_id)
        assert client.post(f"/games/{int(game_id)}/quit", json=_as(seats["GERMANY"], power="GERMANY")).status_code == 200
        r = client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE"))
        assert r.status_code == 200, r.text
        assert (r.json()["game_status"], r.json()["how"]) == ("ACTIVE", None)
        assert game_service.ending(game_id) is None

    def test_making_the_last_open_seat_a_dummy_ends_the_game_with_no_winner(self, client: TestClient) -> None:
        game_id, seats = _game(client, ["FRANCE", "GERMANY"])
        fill_with_dummies(game_id)
        assert client.post(f"/games/{int(game_id)}/quit", json=_as(seats["GERMANY"], power="GERMANY")).status_code == 200
        assert game_service.concede(game_id, "FRANCE")["game_status"] == "ACTIVE"
        with (
            patch("server.api.shared.notify_players") as players,
            patch("server.api.shared.post_to_game_group") as group,
            patch("server.api.routes.games.notify_players") as plain,
        ):
            r = client.post(f"/games/{game_id}/dummies", json={"power": "GERMANY", "dummy": True}, headers=ADMIN)
        assert r.status_code == 200, r.text
        assert (r.json()["ended"], r.json()["winners"]) == ("only_dummies", [])
        assert _status(client, game_id) == {"status": "COMPLETED", "winners": []}
        assert game_service.ending(game_id) == {"winners": [], "how": "only_dummies"}
        text = (
            f"GERMANY is now played by civil disorder, and game {game_id} has ended: "
            "only civil-disorder powers are left, so nobody wins."
        )
        group.assert_called_once_with(game_id, f"🏆 Game {game_id} has ended\n{text}")
        assert players.call_args.args[1] == text
        plain.assert_not_called()

    def test_a_turn_that_eliminates_the_last_human_ends_the_game(self, client: TestClient) -> None:
        """FRANCE, the only player, has an army and no centre going into
        Winter: the adjustment disbands it and only dummies are left."""
        game_id, _ = _game(client, ["FRANCE"])
        fill_with_dummies(game_id)
        state = GameState(
            1901, Season.WINTER, PhaseType.ADJUSTMENT,
            units=frozenset({
                Unit(UnitKind.ARMY, "FRANCE", Location("PIC")),
                Unit(UnitKind.ARMY, "GERMANY", Location("MUN")),
                Unit(UnitKind.ARMY, "ITALY", Location("ROM")),
            }),
            ownership={"MUN": "GERMANY", "ROM": "ITALY"},
        )
        game_service.restore_snapshot(game_id, state_to_dict(state), phase_code=state.phase_name)
        game_service.process_turn(game_id)
        assert game_service.ending(game_id) == {"winners": [], "how": "only_dummies"}
