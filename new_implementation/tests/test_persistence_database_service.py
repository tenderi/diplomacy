"""Direct coverage for persistence.database_service.DatabaseService.

Before PR5 the 1033-LOC DAL had no tests exercising it directly -- everything ran
through the HTTP API. This starts narrow, per the PR5 spec: update_game_deadline
(round trip including None), snapshot create/get, get_players_by_game_id, and an
explicit regression test that commit() is a documented no-op, so nobody
reintroduces the detached-mutation bug that POST /deadline had (routes/games.py
used to mutate a row returned by get_game_by_game_id and then call db_service
.commit(), which does nothing -- the fix was switching to update_game_deadline,
which opens and commits its own session).
"""
import datetime

import pytest

from tests.conftest import _get_db_url
from persistence.database_service import DatabaseService
from persistence.game_repo import GameRepo
from engine.map_loader import load_standard_map
from engine.serialization import state_to_dict
from engine.types import GameState, PhaseType

pytestmark = pytest.mark.skipif(not _get_db_url(), reason="Database not configured")


@pytest.fixture
def db_service() -> DatabaseService:
    return DatabaseService(_get_db_url())


@pytest.fixture
def game_ids(db_service: DatabaseService) -> tuple[str, int]:
    """Create a fresh game via GameRepo (the real creation path -- DatabaseService
    itself has no create_game) and return (game_id string, numeric row id)."""
    repo = GameRepo(db_service.session_factory)
    map_data = load_standard_map()
    state = GameState(
        year=map_data.start_year,
        season=map_data.start_season,
        phase_type=PhaseType.MOVEMENT,
        units=map_data.starting_units,
        ownership=dict(map_data.initial_ownership),
    )
    gid = repo.create(
        map_name="standard",
        state_json=state_to_dict(state),
        phase_code=state.phase_name,
    )
    row = db_service.get_game_by_game_id(gid)
    assert row is not None
    return gid, int(row.id)


class TestUpdateGameDeadline:
    def test_round_trip(self, db_service: DatabaseService, game_ids: tuple[str, int]) -> None:
        _, numeric_id = game_ids
        deadline = datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)
        db_service.update_game_deadline(numeric_id, deadline)
        row = db_service.get_game_by_id(numeric_id)
        assert row is not None
        # games.deadline is a naive TIMESTAMP column; update_game_deadline
        # normalizes to naive UTC before storing (see its docstring), so the
        # round trip is the same instant with tzinfo stripped.
        assert row.deadline == deadline.replace(tzinfo=None)

    def test_none_clears_a_previously_set_deadline(
        self, db_service: DatabaseService, game_ids: tuple[str, int]
    ) -> None:
        _, numeric_id = game_ids
        db_service.update_game_deadline(
            numeric_id, datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)
        )
        db_service.update_game_deadline(numeric_id, None)
        row = db_service.get_game_by_id(numeric_id)
        assert row is not None
        assert row.deadline is None

    def test_unknown_game_id_is_a_silent_noop(self, db_service: DatabaseService) -> None:
        # Matches every other update_* method in the DAL: an id that doesn't
        # exist doesn't raise, it's just a no-op (`if game: ...`).
        db_service.update_game_deadline(999_999_999, datetime.datetime.now(datetime.timezone.utc))


class TestSnapshots:
    def test_create_and_get_round_trip_including_state_json(
        self, db_service: DatabaseService, game_ids: tuple[str, int]
    ) -> None:
        _, numeric_id = game_ids
        view = {
            "units": {"ENGLAND": [{"kind": "F", "province": "LON"}]},
            "supply_centers": {"LON": "ENGLAND"},
        }
        raw_state = {
            "year": 1901, "season": "SPRING", "phase_type": "MOVEMENT",
            "units": [], "ownership": {}, "dislodged": [],
        }
        snap = db_service.create_game_snapshot(
            game_id=numeric_id,
            turn=0,
            year=1901,
            season="SPRING",
            phase="MOVEMENT",
            phase_code="S1901M",
            game_state=view,
            state_json=raw_state,
        )
        assert snap.id is not None

        fetched = db_service.get_game_snapshot_by_id(snap.id, numeric_id)
        assert fetched is not None
        assert fetched.units == view["units"]
        assert fetched.supply_centers == view["supply_centers"]
        assert fetched.state_json == raw_state

    def test_create_without_state_json_leaves_it_null(
        self, db_service: DatabaseService, game_ids: tuple[str, int]
    ) -> None:
        """The pre-PR5 shape: state_json omitted entirely. This is exactly the
        case restore_game_snapshot must reject with 409 rather than silently
        no-op'ing (the old stub's behaviour)."""
        _, numeric_id = game_ids
        snap = db_service.create_game_snapshot(
            game_id=numeric_id, turn=0, year=1901, season="SPRING",
            phase="MOVEMENT", phase_code="S1901M",
            game_state={"units": {}, "supply_centers": {}},
        )
        fetched = db_service.get_game_snapshot_by_id(snap.id, numeric_id)
        assert fetched is not None
        assert fetched.state_json is None

    def test_get_by_id_scoped_to_a_different_game_returns_none(
        self, db_service: DatabaseService, game_ids: tuple[str, int]
    ) -> None:
        _, numeric_id = game_ids
        snap = db_service.create_game_snapshot(
            game_id=numeric_id, turn=0, year=1901, season="SPRING",
            phase="MOVEMENT", phase_code="S1901M",
            game_state={"units": {}, "supply_centers": {}},
        )
        assert db_service.get_game_snapshot_by_id(snap.id, numeric_id + 999_999) is None


class TestPlayers:
    def test_get_players_by_game_id(
        self, db_service: DatabaseService, game_ids: tuple[str, int]
    ) -> None:
        _, numeric_id = game_ids
        assert db_service.get_players_by_game_id(numeric_id) == []
        db_service.create_player(numeric_id, "FRANCE")
        db_service.create_player(numeric_id, "GERMANY")
        players = db_service.get_players_by_game_id(numeric_id)
        assert {p.power_name for p in players} == {"FRANCE", "GERMANY"}


class TestCommitIsANoOp:
    def test_commit_does_not_persist_a_mutation_on_a_detached_row(
        self, db_service: DatabaseService, game_ids: tuple[str, int]
    ) -> None:
        """Regression guard for exactly the bug task 1 (POST /deadline) had:
        mutating an attribute on a row returned by a getter and then calling
        db_service.commit() must NOT persist the change. commit() is a documented
        no-op (sessions are scoped per-method, closed by the time the getter
        returns) -- the only correct way to write a change is a dedicated update_*
        method that opens and commits its own session, as the rest of this file
        exercises. If this assertion ever starts failing because commit() became
        a real commit, every call site that (incorrectly) relies on it being a
        no-op needs re-auditing before that change is accepted.
        """
        _, numeric_id = game_ids
        row = db_service.get_game_by_id(numeric_id)
        assert row is not None
        original_status = row.status
        row.status = "mutated_on_a_detached_instance"
        db_service.commit()
        refetched = db_service.get_game_by_id(numeric_id)
        assert refetched is not None
        assert refetched.status == original_status
