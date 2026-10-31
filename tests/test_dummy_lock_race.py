"""CB1: civil-disorder changes and the endings they can complete, under races.

The BZ1 and BZ4 endings depend on ``dummy_powers``. A seat made a dummy was an
unlocked read-modify-write of that set, and the decisions read it outside any
lock, so a write racing them was lost or left out of the decision.
"""
from __future__ import annotations

import threading
from typing import Any, Optional
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from engine.serialization import state_to_dict
from engine.types import GameState, Location, PhaseType, Season, Unit, UnitKind
from server import game_service as game_service_module
from server.api import app
from server.api.shared import game_service
from server.game_service import GameOverError
from server.response_cache import clear_response_cache
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies
from tests.test_seat_guards import _as, _game

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


@pytest.fixture
def client() -> TestClient:
    clear_response_cache()
    return TestClient(app)


def test_two_seats_made_dummies_at_once_both_stay(client: TestClient) -> None:
    """TURKEY's whole dummy toggle runs while ITALY's is between reading the
    set and writing it. Unlocked, ITALY's write put back the set it had read
    and TURKEY was lost; locked, TURKEY's toggle waits and applies to ITALY's."""
    game_id, _ = _game(client, ["FRANCE"])
    real_check = game_service_module._check_dummy_set
    other: list[Any] = []
    started = threading.Event()
    finished = threading.Event()

    def turkey(gid: str) -> None:
        try:
            other.append(game_service.set_dummy(gid, "TURKEY", True))
        except Exception as e:  # noqa: BLE001 -- handed to the main thread's assertion
            other.append(e)
        finally:
            finished.set()

    def italy_reads_then_turkey_toggles(powers: list[str], map_data: Optional[Any] = None) -> list[str]:
        if not started.is_set():
            started.set()
            threading.Thread(target=turkey, args=(game_id,), daemon=True).start()
            # Unlocked, TURKEY finishes here; locked, it waits for this write.
            finished.wait(timeout=1.0)
        return real_check(powers, map_data)

    with patch.object(game_service_module, "_check_dummy_set", side_effect=italy_reads_then_turkey_toggles):
        italy = game_service.set_dummy(game_id, "ITALY", True)
        assert finished.wait(timeout=10)
    assert italy == {"dummy_powers": ["ITALY"], "ended": None}
    assert other == [{"dummy_powers": ["ITALY", "TURKEY"], "ended": None}]
    assert game_service.dummy_powers(game_id) == frozenset({"ITALY", "TURKEY"})


def test_a_seat_made_a_dummy_mid_turn_ends_the_turn_that_leaves_only_dummies(client: TestClient) -> None:
    """FRANCE, the only player, loses its last unit in this Winter; GERMANY's
    seat is vacant. GERMANY is made a dummy while the turn is adjudicated: its
    own end check sees FRANCE still on the board, and the turn, decided on the
    dummies read before, used to leave GERMANY and ITALY, both dummies, playing
    on. The turn's save is guarded by those dummies and adjudicates again."""
    game_id, seats = _game(client, ["FRANCE", "GERMANY"])
    r = client.post(f"/games/{int(game_id)}/quit", json=_as(seats["GERMANY"], power="GERMANY"))
    assert r.status_code == 200, r.text
    fill_with_dummies(game_id)
    assert "GERMANY" not in game_service.dummy_powers(game_id)
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
    repo = game_service._repo
    real_save = repo.save_state
    toggled: list[dict[str, Any]] = []

    def germany_made_a_dummy_first(gid: str, *args: Any, **kwargs: Any) -> None:
        if not toggled:
            toggled.append(game_service.set_dummy(gid, "GERMANY", True))
        real_save(gid, *args, **kwargs)

    with patch.object(repo, "save_state", side_effect=germany_made_a_dummy_first) as save:
        game_service.process_turn(game_id)
    assert toggled == [{"dummy_powers": ["AUSTRIA", "ENGLAND", "GERMANY", "ITALY", "RUSSIA", "TURKEY"], "ended": None}]
    assert save.call_count == 2
    assert game_service.ending(game_id) == {"winners": [], "how": "only_dummies"}


def test_a_dummy_toggle_on_a_game_drawn_meanwhile_is_the_game_over_error(client: TestClient) -> None:
    """The game ends in a draw after the toggle checked the game was running:
    the toggle is refused, and the finished game's dummies are left alone."""
    game_id, _ = _game(client, ["FRANCE"])
    repo = game_service._repo
    real_players = repo.players

    def players_then_a_draw(gid: str) -> Any:
        seats = real_players(gid)
        drawn = game_service.load(gid).draw()
        repo.save_state(
            gid, state_to_dict(drawn.state), phase_code=drawn.state.phase_name, status="completed"
        )
        return seats

    with patch.object(repo, "players", side_effect=players_then_a_draw), pytest.raises(GameOverError) as e:
        game_service.set_dummy(game_id, "ITALY", True)
    assert str(e.value) == (
        f"Game {game_id} is drawn between AUSTRIA, ENGLAND, FRANCE, GERMANY, ITALY, RUSSIA, TURKEY; "
        "civil-disorder powers can no longer be changed"
    )
    assert game_service.dummy_powers(game_id) == frozenset()

