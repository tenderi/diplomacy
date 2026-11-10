"""``POST /games/{id}/restore/{snapshot_id}``: the admin rollback of a game to a snapshot.

It rewrites the live board, so every guard is pinned: the admin token, a game and a
snapshot that exist (and belong together), a snapshot that carries a ``state_json``,
one that parses, and on success the state, the phase, the pending orders and the draw
votes all belong to the restored phase.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from server.api import ADMIN_TOKEN, app
from server.api import shared as api_shared
from server.api.shared import db_service, game_service
from server.deadline_schedule import parse_schedule
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


def _game(client: TestClient) -> tuple[str, str]:
    """A game with FRANCE and GERMANY seated, the rest dummies (two people, so one
    draw vote does not end it)."""
    tg = _telegram_user(client, "restorer")
    game_id = str(client.post("/games/create", json=_as(tg, map_name="standard"), headers=BOT).json()["game_id"])
    assert client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE")).status_code == 200
    other = _telegram_user(client, "restorer2")
    assert client.post(f"/games/{game_id}/join", json=_as(other, power="GERMANY")).status_code == 200
    fill_with_dummies(game_id)
    return game_id, tg


def _opening_snapshot_id(client: TestClient, game_id: str) -> int:
    snaps = client.get(f"/games/{game_id}/snapshots").json()["snapshots"]
    (opening,) = [s["id"] for s in snaps if s["turn"] == 0]
    return int(opening)


def _snapshot(game_id: str, state_json: object) -> int:
    row = db_service.get_game_by_game_id(game_id)
    snap = db_service.create_game_snapshot(
        game_id=int(row.id), turn=0, year=1901, season="Spring", phase="Movement",
        phase_code="S1901M", game_state={}, state_json=state_json,  # type: ignore[arg-type]
    )
    return int(snap.id)


def _detail(r) -> tuple[int, str]:  # type: ignore[no-untyped-def]
    return r.status_code, r.json()["detail"]


def test_without_the_admin_token_it_is_403(client: TestClient) -> None:
    game_id, _tg = _game(client)
    snap = _opening_snapshot_id(client, game_id)
    expected = (403, "Admin token required to restore a snapshot")
    assert _detail(client.post(f"/games/{game_id}/restore/{snap}")) == expected
    assert _detail(client.post(f"/games/{game_id}/restore/{snap}", headers={"X-Admin-Token": "wrong"})) == expected
    assert _detail(client.post(f"/games/{game_id}/restore/{snap}", headers=BOT)) == expected


def test_a_missing_game_is_404(client: TestClient) -> None:
    assert _detail(client.post("/games/999999999/restore/1", headers=ADMIN)) == (404, "Game not found")


def test_a_missing_snapshot_is_404(client: TestClient) -> None:
    game_id, _tg = _game(client)
    assert _detail(client.post(f"/games/{game_id}/restore/2147483647", headers=ADMIN)) == (404, "Snapshot not found")


def test_another_games_snapshot_is_404(client: TestClient) -> None:
    game_id, _tg = _game(client)
    other_id, _tg2 = _game(client)
    other_snap = _opening_snapshot_id(client, other_id)
    r = client.post(f"/games/{game_id}/restore/{other_snap}", headers=ADMIN)
    assert _detail(r) == (404, "Snapshot not found")


def test_a_snapshot_without_state_json_is_409(client: TestClient) -> None:
    game_id, _tg = _game(client)
    snap = _snapshot(game_id, None)
    r = client.post(f"/games/{game_id}/restore/{snap}", headers=ADMIN)
    assert _detail(r) == (409, "Snapshot predates state_json capture and cannot be restored")


@pytest.mark.parametrize(
    ("state_json", "reason"),
    [
        ({"year": 1901}, "not a game state (KeyError: 'season')"),
        ({"year": 1901, "season": "WINTERISH", "phase_type": "MOVEMENT"},
         "not a game state (ValueError: 'WINTERISH' is not a valid Season)"),
        (["not", "a", "dict"], "not a game state (a list, not an object)"),
    ],
)
def test_a_corrupt_snapshot_is_refused_and_leaves_the_game_alone(
    client: TestClient, state_json: object, reason: str
) -> None:
    game_id, tg = _game(client)
    before = game_service.state_json(game_id)
    client.post("/games/set_orders", json=_as(tg, game_id=game_id, power="FRANCE", orders=["A PAR - BUR"]))
    snap = _snapshot(game_id, state_json)
    r = client.post(f"/games/{game_id}/restore/{snap}", headers=ADMIN)
    assert _detail(r) == (500, f"Corrupt snapshot: {reason}")
    assert game_service.state_json(game_id) == before
    assert game_service.pending_orders_view(game_id) == {"FRANCE": ["A PAR - BUR"]}


def test_a_restore_rolls_back_the_board_and_clears_the_phase_inputs(client: TestClient) -> None:
    game_id, tg = _game(client)
    snap = _opening_snapshot_id(client, game_id)
    opening = db_service.get_game_snapshot_by_id(snap).state_json
    assert client.post("/games/set_orders", json=_as(tg, game_id=game_id, power="FRANCE", orders=["A PAR - BUR"])).status_code == 200
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    assert client.get(f"/games/{game_id}/state").json()["phase"] == "F1901M"
    assert client.post("/games/set_orders", json=_as(tg, game_id=game_id, power="FRANCE", orders=["A BUR - PIC"])).status_code == 200
    game_service.submit_draw_vote(game_id, "FRANCE", True)
    assert game_service.get_draw_votes(game_id)["votes"] == ["FRANCE"]

    r = client.post(f"/games/{game_id}/restore/{snap}", headers=ADMIN)
    assert (r.status_code, r.json()) == (200, {"status": "ok", "snapshot_id": snap, "phase_code": "S1901M"})

    assert game_service.state_json(game_id) == opening
    assert db_service.get_game_by_game_id(game_id).phase_code == "S1901M"
    assert game_service.pending_orders_view(game_id) == {}
    assert game_service.get_draw_votes(game_id)["votes"] == []
    state = client.get(f"/games/{game_id}/state").json()
    assert state["phase"] == "S1901M"
    assert "A PAR" in [f"{u['kind']} {u['location']}" for u in state["units_by_power"]["FRANCE"]]


def _deadline(game_id: str) -> datetime | None:
    deadline = db_service.get_game_by_game_id(game_id).deadline
    return None if deadline is None else deadline.replace(tzinfo=timezone.utc)


def test_a_restore_drops_the_discarded_phases_deadline(client: TestClient) -> None:
    """CP4: a deadline set for F1901M is that phase's; left in place it would make
    the scheduler process the restored S1901M at F1901M's deadline -- here, at
    once, with nobody's orders in."""
    game_id, _tg = _game(client)
    snap = _opening_snapshot_id(client, game_id)
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    row = db_service.get_game_by_game_id(game_id)
    db_service.update_game_deadline(int(row.id), datetime.now(timezone.utc) - timedelta(minutes=1))

    assert client.post(f"/games/{game_id}/restore/{snap}", headers=ADMIN).status_code == 200

    assert _deadline(game_id) is None
    api_shared.process_due_deadlines(datetime.now(timezone.utc))
    assert db_service.get_game_by_game_id(game_id).phase_code == "S1901M"


def test_a_restore_arms_the_restored_phases_scheduled_deadline(client: TestClient) -> None:
    """With a weekly schedule the restored phase gets the next slot, as a phase
    entered by a processed turn does -- not the discarded phase's deadline."""
    game_id, _tg = _game(client)
    snap = _opening_snapshot_id(client, game_id)
    row = db_service.get_game_by_game_id(game_id)
    schedule = parse_schedule("mon,wed,fri 16:00", "UTC")
    db_service.update_game_deadline_schedule(int(row.id), schedule.to_json())
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    db_service.update_game_deadline(int(row.id), datetime.now(timezone.utc) + timedelta(days=30))

    before = datetime.now(timezone.utc)
    assert client.post(f"/games/{game_id}/restore/{snap}", headers=ADMIN).status_code == 200
    after = datetime.now(timezone.utc)

    # The same slot unless the request straddled a slot's one-hour notice cut-off.
    assert _deadline(game_id) in {schedule.next_deadline(before), schedule.next_deadline(after)}
    assert _deadline(game_id) < datetime.now(timezone.utc) + timedelta(days=3)


def _hold_and_process(client: TestClient, game_id: str, tg: str) -> None:
    assert client.post("/games/set_orders", json=_as(tg, game_id=game_id, power="FRANCE", orders=["A PAR H"])).status_code == 200
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200


def _turns(game_id: str) -> tuple[int, list[str], list[str], list[int]]:
    row = db_service.get_game_by_game_id(game_id)
    snaps = sorted(int(s.turn_number) for s in db_service.get_game_snapshots_by_game_id(int(row.id)))
    return int(row.current_turn), sorted(row.order_history or {}), sorted(row.resolution_history or {}), snaps


def test_a_restore_rewinds_the_turn_counter_and_the_per_turn_histories(client: TestClient) -> None:
    """DE1: rolled back from turn 3 to turn 1, the game's turn record is turn 1's:
    the counter, the histories (turn 0's entry only -- turn 1's orders are about to be
    replayed), ``last_resolution`` (turn 0's, which produced the restored board) and the
    snapshots. The next processed turn is stored as turn 1 again, not 3."""
    game_id, tg = _game(client)
    for _ in range(3):
        _hold_and_process(client, game_id, tg)
    assert _turns(game_id) == (3, ["0", "1", "2"], ["0", "1", "2"], [0, 1, 2, 3])
    row = db_service.get_game_by_game_id(game_id)
    turn_0_resolution = row.resolution_history["0"]
    (snap,) = [s.id for s in db_service.get_game_snapshots_by_game_id(int(row.id)) if s.turn_number == 1]

    assert client.post(f"/games/{game_id}/restore/{snap}", headers=ADMIN).status_code == 200

    assert _turns(game_id) == (1, ["0"], ["0"], [0, 1])
    assert db_service.get_game_by_game_id(game_id).last_resolution == turn_0_resolution
    resolutions = client.get(f"/games/{game_id}/resolutions").json()["resolutions"]
    assert list(resolutions) == ["0"]
    assert client.get(f"/games/{game_id}/last_resolution").json()["results"] == resolutions["0"]["results"]
    assert client.get(f"/games/{game_id}/history/2").status_code == 404

    _hold_and_process(client, game_id, tg)
    assert _turns(game_id) == (2, ["0", "1"], ["0", "1"], [0, 1, 2])
    assert db_service.get_game_by_game_id(game_id).phase_code == "S1902M"


def test_a_restore_to_the_opening_board_has_no_last_resolution(client: TestClient) -> None:
    game_id, tg = _game(client)
    snap = _opening_snapshot_id(client, game_id)
    _hold_and_process(client, game_id, tg)
    assert db_service.get_game_by_game_id(game_id).last_resolution is not None

    assert client.post(f"/games/{game_id}/restore/{snap}", headers=ADMIN).status_code == 200

    assert _turns(game_id) == (0, [], [], [0])
    assert db_service.get_game_by_game_id(game_id).last_resolution is None


def test_a_restore_clears_the_reminder_of_the_discarded_deadline(client: TestClient) -> None:
    """Every write of ``deadline`` clears ``reminded_deadline`` (data_spec): the
    restore's own, before any route re-arms it (the saved-game import does not)."""
    game_id, _tg = _game(client)
    row = db_service.get_game_by_game_id(game_id)
    deadline = datetime.now(timezone.utc) + timedelta(minutes=5)
    db_service.update_game_deadline(int(row.id), deadline)
    assert db_service.claim_deadline_reminder(int(row.id), deadline) is True

    game_service.restore_snapshot(game_id, game_service.state_json(game_id), "S1901M")

    row = db_service.get_game_by_game_id(game_id)
    assert (row.deadline, row.reminded_deadline) == (None, None)


def test_a_draw_ends_the_game_without_counting_a_turn(client: TestClient) -> None:
    """DE1: ending a game outside a turn (here a draw) adjudicates nothing, so the
    turn counter stays on the last turn that has a snapshot and a history entry."""
    game_id, tg = _game(client)
    _hold_and_process(client, game_id, tg)
    assert _turns(game_id) == (1, ["0"], ["0"], [0, 1])

    game_service.submit_draw_vote(game_id, "FRANCE", True)
    game_service.submit_draw_vote(game_id, "GERMANY", True)

    assert db_service.get_game_by_game_id(game_id).status == "completed"
    assert _turns(game_id) == (1, ["0"], ["0"], [0, 1])
