"""#461: the migration that drops the tournament and spectator tables (and
``games.observer_mode``) round-trips.

The downgrade recreates the four tables empty, the upgrade drops them again, and the
upgrade refuses to drop a table that still holds a row instead of losing it.
"""
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from tests.conftest import _get_db_url

pytestmark = [
    pytest.mark.database,
    pytest.mark.skipif(not _get_db_url(), reason="Database not configured"),
]

ROOT = Path(__file__).resolve().parent.parent
TABLES = {"tournaments", "tournament_games", "tournament_players", "spectators"}
REVISION = "b6d2e3f4a5b6"


def _alembic(fn: str, target: str) -> None:
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        getattr(command, fn)(Config(str(ROOT / "alembic.ini")), target)
    finally:
        os.chdir(cwd)


def _tables() -> set[str]:
    engine = create_engine(_get_db_url())
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _games_columns() -> set[str]:
    engine = create_engine(_get_db_url())
    try:
        return {c["name"] for c in inspect(engine).get_columns("games")}
    finally:
        engine.dispose()


@pytest.fixture
def downgraded() -> Iterator[None]:
    """The schema one step before the drop; restored to head afterwards."""
    _alembic("upgrade", "head")
    _alembic("downgrade", f"{REVISION}-1")
    try:
        yield
    finally:
        engine = create_engine(_get_db_url())
        with engine.begin() as conn:
            if "tournaments" in set(inspect(conn).get_table_names()):
                conn.execute(text("DELETE FROM tournaments"))
        engine.dispose()
        _alembic("upgrade", "head")


def test_the_drop_round_trips(downgraded: None) -> None:
    assert TABLES <= _tables()
    assert "observer_mode" in _games_columns()
    _alembic("upgrade", "head")
    assert TABLES & _tables() == set()
    assert "observer_mode" not in _games_columns()


def test_the_upgrade_refuses_to_drop_a_table_holding_a_row(downgraded: None) -> None:
    engine = create_engine(_get_db_url())
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO tournaments (name) VALUES ('kept')"))
    engine.dispose()
    with pytest.raises(RuntimeError, match="Table tournaments is not empty"):
        _alembic("upgrade", "head")
    assert TABLES <= _tables()
