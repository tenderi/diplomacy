"""CC3: a seat taken and the same seat made a dummy, at once.

``set_dummy`` checked that the seat was empty by reading the players outside
the game-row lock, and a join wrote its seat without taking that lock, so the
two could both succeed: a seat a player holds, played by civil disorder. Both
now decide on the ``games`` row taken ``FOR UPDATE``; whichever goes second
sees the other and is refused.
"""
from __future__ import annotations

import threading
from typing import Any, Optional
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from persistence import database_service as database_service_module
from server import game_service as game_service_module
from server.api import app
from server.api.shared import db_service, game_service
from server.game_service import OrderError
from server.response_cache import clear_response_cache
from tests.conftest import _get_db_url
from tests.test_seat_guards import _as, _game, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


@pytest.fixture
def client() -> TestClient:
    clear_response_cache()
    return TestClient(app)


def _holder(game_id: str, power: str) -> Optional[int]:
    seat = db_service.get_player_by_game_id_and_power(game_id=int(game_id), power=power)
    return None if seat is None else seat.user_id


def _dummy_message(game_id: str) -> str:
    return f"ITALY is played by civil disorder in game {game_id}; the game's creator can open it."


def _race_a_seat_write_against_the_toggle(
    game_id: str, path: str, body: dict[str, object]
) -> tuple[dict[str, Any], list[Any]]:
    """ITALY is made a dummy; while its toggle holds the game-row lock,
    another thread posts ``body`` to ``path``. Unlocked, that write finished
    meanwhile; locked, it waits for the toggle and then sees the dummy."""
    real_check = game_service_module._check_dummy_set
    other: list[Any] = []
    started = threading.Event()
    finished = threading.Event()

    def take_the_seat() -> None:
        try:
            other.append(TestClient(app).post(path, json=body))
        except Exception as e:  # noqa: BLE001 -- handed to the main thread's assertion
            other.append(e)
        finally:
            finished.set()

    def toggle_holds_the_lock(powers: list[str], map_data: Optional[Any] = None) -> list[str]:
        if not started.is_set():
            started.set()
            threading.Thread(target=take_the_seat, daemon=True).start()
            # Unlocked, the seat write finishes here; locked, it waits for this one.
            finished.wait(timeout=1.0)
        return real_check(powers, map_data)

    with patch.object(game_service_module, "_check_dummy_set", side_effect=toggle_holds_the_lock):
        toggled = game_service.set_dummy(game_id, "ITALY", True)
        assert finished.wait(timeout=10)
    return toggled, other


def test_a_join_racing_the_toggle_is_refused(client: TestClient) -> None:
    game_id, _ = _game(client, ["FRANCE"])
    tg = _telegram_user(client)
    toggled, other = _race_a_seat_write_against_the_toggle(
        game_id, f"/games/{game_id}/join", _as(tg, power="ITALY")
    )
    assert toggled == {"dummy_powers": ["ITALY"], "ended": None}
    assert [(r.status_code, r.json()["detail"]) for r in other] == [(409, _dummy_message(game_id))]
    assert _holder(game_id, "ITALY") is None
    assert game_service.dummy_powers(game_id) == frozenset({"ITALY"})


def test_a_replace_racing_the_toggle_is_refused(client: TestClient) -> None:
    game_id, seats = _game(client, ["FRANCE", "ITALY"])
    r = client.post(f"/games/{int(game_id)}/quit", json=_as(seats["ITALY"], power="ITALY"))
    assert r.status_code == 200, r.text
    tg = _telegram_user(client)
    toggled, other = _race_a_seat_write_against_the_toggle(
        game_id, f"/games/{game_id}/replace", _as(tg, power="ITALY")
    )
    assert toggled == {"dummy_powers": ["ITALY"], "ended": None}
    assert [(r.status_code, r.json()["detail"]) for r in other] == [(409, _dummy_message(game_id))]
    assert _holder(game_id, "ITALY") is None


def test_a_toggle_racing_a_join_sees_the_seat_taken(client: TestClient) -> None:
    """The join holds the game-row lock when the toggle starts: the toggle
    waits, reads the seat the join wrote, and refuses it."""
    game_id, _ = _game(client, ["FRANCE"])
    tg = _telegram_user(client)
    real_lock = database_service_module._lock_game_refusing_dummy
    other: list[Any] = []
    started = threading.Event()
    finished = threading.Event()

    def toggle() -> None:
        try:
            other.append(game_service.set_dummy(game_id, "ITALY", True))
        except Exception as e:  # noqa: BLE001 -- handed to the main thread's assertion
            other.append(e)
        finally:
            finished.set()

    def join_holds_the_lock(session: Any, gid: int, power: str) -> None:
        real_lock(session, gid, power)
        if not started.is_set():
            started.set()
            threading.Thread(target=toggle, daemon=True).start()
            # Unlocked, the toggle finishes here; locked, it waits for this join.
            finished.wait(timeout=1.0)

    with patch.object(database_service_module, "_lock_game_refusing_dummy", side_effect=join_holds_the_lock):
        r = client.post(f"/games/{game_id}/join", json=_as(tg, power="ITALY"))
        assert finished.wait(timeout=10)
    assert r.status_code == 200, r.text
    assert len(other) == 1
    assert isinstance(other[0], OrderError)
    assert str(other[0]) == "ITALY is held by a player; only an empty seat can be a dummy"
    assert game_service.dummy_powers(game_id) == frozenset()
    assert _holder(game_id, "ITALY") is not None
