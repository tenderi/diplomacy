"""BL6: a game ends when one power, or none, is left -- by any route.

A concession leaving one power already ended the game (BL2). A processed turn
that wiped out the last opponent left it ACTIVE until somebody reached 18
centres, and the last two powers conceding at the same moment left an ACTIVE
game with no units at all. A turn that ends the game also has to refresh every
player's cached game list.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from engine.serialization import state_from_dict, state_to_dict
from engine.types import GameState, GameStatus, Location, PhaseType, Season, Unit, UnitKind
from server.api import app
from server.api.shared import game_service
from server.game_service import GameService
from server.response_cache import clear_response_cache
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies
from tests.test_seat_guards import BOT, _as, _game

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

OTHERS = ("AUSTRIA", "ENGLAND", "ITALY", "RUSSIA", "TURKEY")


@pytest.fixture
def client() -> TestClient:
    clear_response_cache()
    return TestClient(app)


def _france_and_germany(client: TestClient) -> tuple[str, dict[str, str]]:
    """FRANCE and GERMANY seated, the five dummies conceded: two powers left."""
    game_id, seats = _game(client, ["FRANCE", "GERMANY"])
    fill_with_dummies(game_id)
    for power in OTHERS:
        assert game_service.concede(game_id, power)["game_status"] == "ACTIVE"
    return game_id, seats


def _army(power: str, province: str) -> Unit:
    return Unit(UnitKind.ARMY, power, Location(province))


def _put(game_id: str, state: GameState) -> None:
    game_service.restore_snapshot(game_id, state_to_dict(state), phase_code=state.phase_name)


def _listed_status(client: TestClient, tg: str, game_id: str) -> list[str]:
    games = client.get(f"/users/{tg}/games", headers=BOT).json()["games"]
    return [g["status"] for g in games if str(g["game_id"]) == game_id]


def test_a_turn_that_wipes_out_the_last_opponent_ends_the_game(client: TestClient) -> None:
    """GERMANY has an army and no centre going into Winter: the adjustment
    disbands it, and FRANCE, with two centres, is the last power standing."""
    game_id, seats = _france_and_germany(client)
    _put(game_id, GameState(
        1901, Season.WINTER, PhaseType.ADJUSTMENT,
        units=frozenset({_army("FRANCE", "PAR"), _army("GERMANY", "RUH")}),
        ownership={"PAR": "FRANCE", "MAR": "FRANCE"},
    ))
    for tg in seats.values():  # warm each player's cached game list
        assert _listed_status(client, tg, game_id) == ["active"]

    with (
        patch("server.api.shared.notify_players") as players,
        patch("server.api.shared._post_turn_to_channel") as channel,
    ):
        r = client.post(f"/games/{game_id}/process_turn", headers=BOT)
    assert r.status_code == 200, r.text
    assert (r.json()["phase"], r.json()["game_status"]) == ("S1902M", "COMPLETED")
    state = client.get(f"/games/{game_id}/state").json()
    assert (state["status"], state["winners"]) == ("COMPLETED", ["FRANCE"])
    assert game_service.meta(game_id)["status"] == "completed"
    assert game_service.ending(game_id) == {"winners": ["FRANCE"], "how": "last_standing"}

    ended = f"Game {game_id} has ended"
    (_numeric, text), kwargs = players.call_args
    assert players.call_count == 1  # one message: the turn result is the end
    assert text == f"{ended}: FRANCE is the last power standing and wins."
    assert kwargs["own"](["FRANCE"]) == f"{ended}: you are the last power standing and win."
    assert kwargs["own"](["GERMANY"]) is None
    assert channel.call_args.args[1] == f"The turn has been processed. {ended}: FRANCE is the last power standing and wins."
    for tg in seats.values():
        assert _listed_status(client, tg, game_id) == ["completed"]


def test_a_solo_victory_refreshes_every_players_game_list(client: TestClient) -> None:
    """BL5: an 18-centre win by a processed turn left each player's cached
    game list showing the game as active."""
    game_id, seats = _france_and_germany(client)
    seventeen = "PAR MAR BRE SPA POR BEL HOL LON LVP EDI NWY SWE DEN ROM NAP VEN TUN".split()
    _put(game_id, GameState(
        1901, Season.FALL, PhaseType.MOVEMENT,
        units=frozenset({_army("FRANCE", "MUN"), _army("GERMANY", "BER")}),
        ownership={**{c: "FRANCE" for c in seventeen}, "BER": "GERMANY", "KIE": "GERMANY"},
    ))
    for tg in seats.values():
        assert _listed_status(client, tg, game_id) == ["active"]

    with patch("server.api.shared.notify_players") as players, patch("server.api.shared._post_turn_to_channel"):
        r = client.post(f"/games/{game_id}/process_turn", headers=BOT)
    assert r.status_code == 200, r.text
    assert r.json()["game_status"] == "COMPLETED"
    for tg in seats.values():
        assert _listed_status(client, tg, game_id) == ["completed"]
    assert game_service.ending(game_id) == {"winners": ["FRANCE"], "how": "solo"}
    assert players.call_args.args[1] == f"Game {game_id} has ended: FRANCE has won with a solo victory."


def test_the_last_two_conceding_together_end_the_game_without_a_winner(client: TestClient) -> None:
    """GERMANY's concession lands between FRANCE's and FRANCE's end check: nobody
    is left. The game used to stay ACTIVE with no units on the board."""
    game_id, seats = _france_and_germany(client)
    original = GameService._end_if_last_standing
    raced: list[bool] = []

    def germany_concedes_meanwhile(service: GameService, gid: str) -> Any:
        if not raced:  # GERMANY's write, as its own request would make it
            raced.append(True)

            def without_germany(current: dict[str, Any]) -> dict[str, Any]:
                state = state_from_dict(current)
                return state_to_dict(GameState(
                    state.year, state.season, state.phase_type,
                    units=frozenset(u for u in state.units if u.power != "GERMANY"),
                    ownership={p: o for p, o in state.ownership.items() if o != "GERMANY"},
                ))

            service._repo.modify_state_json(gid, without_germany, expected_phase_code="S1901M")
        return original(service, gid)

    with (
        patch.object(GameService, "_end_if_last_standing", autospec=True, side_effect=germany_concedes_meanwhile),
        patch("server.api.shared.notify_players") as players,
        patch("server.api.shared.post_to_game_group") as group,
        patch("server.api.routes.games.notify_players") as play_on,
    ):
        r = client.post(f"/games/{game_id}/concede", json=_as(seats["FRANCE"], power="FRANCE"))
    assert r.status_code == 200, r.text
    assert r.json() == {
        "status": "ok", "power": "FRANCE", "game_status": "COMPLETED", "eliminated": True,
        "winners": [], "auto_processed": False,
    }
    state = client.get(f"/games/{game_id}/state").json()
    assert (state["status"], state["winners"], state["units"]) == ("COMPLETED", [], [])
    assert game_service.ending(game_id) == {"winners": [], "how": "no_winner"}

    text = f"FRANCE has conceded, and game {game_id} has ended: no power is left, so nobody wins."
    play_on.assert_not_called()
    (_numeric, sent), kwargs = players.call_args
    assert (players.call_count, sent) == (1, text)
    assert kwargs["own"](["GERMANY"]) is None
    group.assert_called_once_with(game_id, f"🏆 Game {game_id} has ended\n{text}")
    # And it is over: nothing more can be played.
    r = client.post(f"/games/{game_id}/process_turn", headers=BOT)
    assert (r.status_code, r.json()["detail"]) == (
        409, f"Game {game_id} is over; the turn cannot be processed",
    )


def test_a_turn_with_no_power_left_says_nobody_wins() -> None:
    """``notify_turn_processed`` for a game that ended with no winners."""
    game_id, _seats = _game(TestClient(app), ["FRANCE"])
    _put(game_id, GameState(
        1901, Season.SPRING, PhaseType.MOVEMENT, status=GameStatus.COMPLETED, winners=frozenset(),
    ))
    from server.api import shared

    with patch("server.api.shared.notify_players") as players, patch("server.api.shared._post_turn_to_channel"):
        shared.notify_turn_processed(game_id, 0, trigger="manual", game_ended=True)
    assert players.call_args.args[1] == f"Game {game_id} has ended: no power is left, so nobody wins."
    assert players.call_args.kwargs["own"](["FRANCE"]) is None
