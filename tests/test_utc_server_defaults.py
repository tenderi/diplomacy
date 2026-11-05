"""CP5: a naive ``TIMESTAMP`` column's server default stores UTC.

``DEFAULT now()`` on a naive column stores the session timezone's wall time, so
a raw-SQL insert from a non-UTC session was shifted. The defaults are
``timezone('UTC', now())`` instead; these tests insert through a connection in
Asia/Tokyo (UTC+9) and read the stored default back.
"""
from collections.abc import Iterator
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, text

from persistence.database import UTC_NOW, Base, utcnow_naive
from tests.conftest import _get_db_url

pytestmark = [
    pytest.mark.database,
    pytest.mark.skipif(not _get_db_url(), reason="Database not configured"),
]

SLACK = timedelta(minutes=1)


@pytest.fixture
def tokyo() -> Iterator[Engine]:
    engine = create_engine(_get_db_url(), connect_args={"options": "-c timezone=Asia/Tokyo"})
    with engine.connect() as conn:
        assert conn.execute(text("SHOW TIME ZONE")).scalar() == "Asia/Tokyo"
    yield engine
    engine.dispose()


def test_a_raw_sql_insert_from_a_tokyo_session_stores_utc_defaults(tokyo: Engine) -> None:
    game_id = f"cp5-{uuid4().hex[:8]}"
    name = f"cp5-{uuid4().hex[:8]}"
    with tokyo.begin() as conn:
        game_created, game_updated = conn.execute(
            text(
                "INSERT INTO games (game_id, map_name) VALUES (:g, 'standard') "
                "RETURNING created_at, updated_at"
            ),
            {"g": game_id},
        ).one()
        tournament_created = conn.execute(
            text("INSERT INTO tournaments (name) VALUES (:n) RETURNING created_at"), {"n": name}
        ).scalar_one()
        expected = utcnow_naive()
        conn.execute(text("DELETE FROM tournaments WHERE name = :n"), {"n": name})
        conn.execute(text("DELETE FROM games WHERE game_id = :g"), {"g": game_id})
    for stored in (game_created, game_updated, tournament_created):
        assert stored.tzinfo is None
        assert abs(stored - expected) < SLACK, f"stored {stored}, expected about {expected} (naive UTC)"


def test_no_naive_timestamp_column_defaults_to_bare_now(tokyo: Engine) -> None:
    with tokyo.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name, column_name, column_default FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND data_type = 'timestamp without time zone' "
                "AND (column_default ILIKE '%now()%' OR column_default ILIKE '%current_timestamp%') "
                "ORDER BY table_name, column_name"
            )
        ).all()
    bare = [(t, c, d) for t, c, d in rows if d != "timezone('UTC'::text, now())"]
    assert bare == []
    # The models declare the same defaults, so a create_all schema matches the migrated one.
    declared = {
        (table.name, column.name)
        for table in Base.metadata.tables.values()
        for column in table.columns
        if column.server_default is not None and column.server_default.arg is UTC_NOW
    }
    assert declared == {(t, c) for t, c, _ in rows}
    assert len(declared) == 11
