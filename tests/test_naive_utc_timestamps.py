"""CP2: every ``datetime`` column is a naive ``TIMESTAMP`` holding UTC.

Handing Postgres a tz-aware value for such a column makes it convert the value
to the connection's session timezone and store that wall time. These tests run
the DAL over a connection whose session timezone is Asia/Tokyo (UTC+9) and
read the stored values back raw: an aware write shows up nine hours ahead.
"""
from datetime import datetime, timedelta
from typing import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from engine.map_loader import load_standard_map
from engine.serialization import state_to_dict
from engine.types import GameState, PhaseType
from persistence.database import utcnow_naive
from persistence.database_service import DatabaseService
from persistence.game_repo import GameRepo
from tests.conftest import _get_db_url

pytestmark = pytest.mark.skipif(not _get_db_url(), reason="Database not configured")

SLACK = timedelta(minutes=1)


@pytest.fixture
def tokyo() -> Iterator[DatabaseService]:
    """A ``DatabaseService`` whose every connection runs in Asia/Tokyo."""
    engine = create_engine(_get_db_url(), connect_args={"options": "-c timezone=Asia/Tokyo"})
    service = DatabaseService.__new__(DatabaseService)
    service.session_factory = sessionmaker(bind=engine)
    with service.session_factory() as session:
        assert session.execute(text("SHOW TIME ZONE")).scalar() == "Asia/Tokyo"
    yield service
    engine.dispose()


def _raw(service: DatabaseService, sql: str, **params: object) -> datetime:
    with service.session_factory() as session:
        value = session.execute(text(sql), params).scalar()
    assert isinstance(value, datetime) and value.tzinfo is None
    return value


def _assert_utc(stored: datetime, expected: datetime) -> None:
    assert abs(stored - expected) < SLACK, f"stored {stored}, expected about {expected} (naive UTC)"


def _new_game(repo: GameRepo) -> tuple[str, dict[str, object]]:
    map_data = load_standard_map()
    state = GameState(
        year=map_data.start_year,
        season=map_data.start_season,
        phase_type=PhaseType.MOVEMENT,
        units=map_data.starting_units,
        ownership=dict(map_data.initial_ownership),
    )
    state_json = state_to_dict(state)
    return repo.create(map_name="standard", state_json=state_json, phase_code="S1901M"), state_json


def _updated_at(service: DatabaseService, game_id: str) -> datetime:
    return _raw(service, "SELECT updated_at FROM games WHERE game_id = :g", g=game_id)


def test_game_writes_stamp_updated_at_in_naive_utc(tokyo: DatabaseService) -> None:
    repo = GameRepo(tokyo.session_factory)
    game_id, state_json = _new_game(repo)

    repo.save_state(game_id, state_json, phase_code="S1901M", status="active", expected_phase_code="S1901M")
    _assert_utc(_updated_at(tokyo, game_id), utcnow_naive())

    repo.modify_state_json(game_id, lambda s: s, expected_phase_code="S1901M")
    _assert_utc(_updated_at(tokyo, game_id), utcnow_naive())

    repo.restore_state(game_id, state_json, phase_code="S1901M")
    _assert_utc(_updated_at(tokyo, game_id), utcnow_naive())


def _user(service: DatabaseService) -> int:
    stamp = utcnow_naive().strftime("%H%M%S%f")
    return int(service.create_user_with_password(f"cp2-{stamp}@example.com", "x").id)


def test_link_code_expiry_is_stored_in_naive_utc_and_honoured(tokyo: DatabaseService) -> None:
    user_id = _user(tokyo)
    code, _ = tokyo.create_link_code(user_id, ttl_minutes=10)
    stored = _raw(tokyo, "SELECT expires_at FROM link_codes WHERE code = :c", c=code)
    _assert_utc(stored, utcnow_naive() + timedelta(minutes=10))
    assert tokyo.consume_link_code(code) == user_id


def test_reset_token_expiry_is_stored_in_naive_utc_and_honoured(tokyo: DatabaseService) -> None:
    user_id = _user(tokyo)
    token = tokyo.create_password_reset_token(user_id, ttl_minutes=60)
    stored = _raw(tokyo, "SELECT expires_at FROM password_reset_tokens WHERE token = :t", t=token)
    _assert_utc(stored, utcnow_naive() + timedelta(minutes=60))
    assert tokyo.consume_password_reset_token(token) == user_id


def test_a_naive_utc_expiry_is_compared_in_utc(tokyo: DatabaseService) -> None:
    """A code written correctly (naive UTC, two hours left) is still valid
    when consumed over a Tokyo connection: comparing it with an aware "now"
    would read it as Tokyo wall time, seven hours in the past."""
    utc_service = DatabaseService(_get_db_url())
    user_id = _user(utc_service)
    code = f"cp2{utcnow_naive().strftime('%M%S%f')}"
    with utc_service.session_factory() as session:
        session.execute(
            text("INSERT INTO link_codes (user_id, code, expires_at) VALUES (:u, :c, :e)"),
            {"u": user_id, "c": code, "e": utcnow_naive() + timedelta(hours=2)},
        )
        session.commit()
    assert tokyo.consume_link_code(code) == user_id
