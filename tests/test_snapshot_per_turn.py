"""DE4: ``map_snapshots`` holds exactly one row per (game, turn).

The row for the board a processed turn reaches used to be written by
``finish_processed_turn``, in a later transaction than the turn itself, under a
re-read ``current_turn``: an admin restore landing in between left a second
turn-``t`` row carrying the discarded board, and ``/history/{t}`` read whichever
row Postgres returned first. Now the turn's own transaction writes it, and a
unique ``(game_id, turn_number)`` makes every other writer replace, not add.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from persistence.database import MapSnapshotModel
from server.api import ADMIN_TOKEN, app
from server.api import shared as api_shared
from server.api.shared import db_service, game_service
from server.response_cache import clear_response_cache
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

BOT = {"X-Bot-Secret": BOT_SECRET}
ADMIN = {"X-Admin-Token": ADMIN_TOKEN}


@pytest.fixture
def client() -> TestClient:
    clear_response_cache()
    return TestClient(app)


def _game(client: TestClient) -> tuple[str, int]:
    tg = _telegram_user(client, "snapper")
    game_id = str(client.post("/games/create", json=_as(tg, map_name="standard"), headers=BOT).json()["game_id"])
    assert client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE")).status_code == 200
    fill_with_dummies(game_id)
    return game_id, int(db_service.get_game_by_game_id(game_id).id)


def _rows(numeric_id: int) -> list[tuple[int, str]]:
    return sorted(
        (int(s.turn_number), str(s.phase_code)) for s in db_service.get_game_snapshots_by_game_id(numeric_id)
    )


def test_the_turn_itself_writes_the_snapshot_of_the_board_it_reaches(client: TestClient) -> None:
    game_id, numeric_id = _game(client)
    game_service.process_turn(game_id)
    assert _rows(numeric_id) == [(0, "S1901M"), (1, "F1901M")]


def test_a_restore_between_the_turn_and_its_follow_up_leaves_one_row_per_turn(client: TestClient) -> None:
    game_id, numeric_id = _game(client)
    (opening,) = [s for s in db_service.get_game_snapshots_by_game_id(numeric_id) if s.turn_number == 0]
    game_service.process_turn(game_id)
    # An admin restore of the opening board lands before the turn's follow-up.
    assert client.post(f"/games/{game_id}/restore/{opening.id}", headers=ADMIN).status_code == 200
    api_shared.finish_processed_turn(game_id, numeric_id, prev_phase_code="S1901M", trigger="manual")
    assert _rows(numeric_id) == [(0, "S1901M")]
    history = client.get(f"/games/{game_id}/history/0").json()
    assert history["phase_code"] == "S1901M"


def test_a_second_snapshot_of_a_turn_replaces_the_first(client: TestClient) -> None:
    game_id, numeric_id = _game(client)
    (opening,) = db_service.get_game_snapshots_by_game_id(numeric_id)
    db_service.update_game_snapshot_map_image_path(int(opening.id), "/tmp/diplomacy_maps/old.png")
    snap = db_service.create_game_snapshot(
        game_id=numeric_id, turn=0, year=1901, season="Spring", phase="Movement",
        phase_code="S1901M", game_state={"units": {"FRANCE": ["A PAR"]}, "supply_centers": {}},
    )
    assert snap.id == opening.id
    snap = db_service.get_game_snapshot_by_game_id_and_turn(numeric_id, 0)
    assert snap.units == {"FRANCE": ["A PAR"]}
    # Kept, so the cleanup job still finds (and deletes) the old image.
    assert snap.map_image_path == "/tmp/diplomacy_maps/old.png"
    assert _rows(numeric_id) == [(0, "S1901M")]


def test_the_snapshot_route_adds_a_missing_turn_and_never_rewrites_one(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, numeric_id = _game(client)
    (opening,) = db_service.get_game_snapshots_by_game_id(numeric_id)
    first = client.post(f"/games/{game_id}/snapshot", headers=BOT).json()
    assert (first["turn"], first["snapshot_id"]) == (0, opening.id)
    stale_view, stale_state = game_service.view(game_id), game_service.state_json(game_id)
    game_service.process_turn(game_id)
    # The turn lands after the route read the board but before it read the turn.
    monkeypatch.setattr(game_service, "view", lambda _gid: stale_view)
    monkeypatch.setattr(game_service, "state_json", lambda _gid: stale_state)
    second = client.post(f"/games/{game_id}/snapshot", headers=BOT).json()
    assert second["turn"] == 1
    assert _rows(numeric_id) == [(0, "S1901M"), (1, "F1901M")]
    # A row the turn did not write (a game imported without it) is added.
    with db_service.session_factory() as session:
        session.query(MapSnapshotModel).filter_by(game_id=numeric_id, turn_number=1).delete()
        session.commit()
    monkeypatch.undo()
    third = client.post(f"/games/{game_id}/snapshot", headers=BOT).json()
    assert third["turn"] == 1
    assert _rows(numeric_id) == [(0, "S1901M"), (1, "F1901M")]


def test_the_table_refuses_a_second_row_for_a_turn(client: TestClient) -> None:
    _game_id, numeric_id = _game(client)
    with db_service.session_factory() as session:
        session.add(MapSnapshotModel(
            game_id=numeric_id, turn_number=0, phase_code="S1901M", units={}, supply_centers={},
        ))
        with pytest.raises(IntegrityError):
            session.commit()
