"""Default naive TIMESTAMP columns to UTC, not the session timezone's wall time

Every ``datetime`` column is a naive ``TIMESTAMP`` holding UTC. Earlier
revisions gave these columns ``DEFAULT now()``; ``now()`` is a timestamptz, and
casting it to a naive column stores the connection's session-timezone wall
time, so a raw-SQL insert from a non-UTC session stored a shifted value. The
ORM always supplies ``utcnow_naive()``, so only raw SQL reached the default.
``timezone('UTC', now())`` yields the UTC wall time whatever the session
timezone. The list is every naive column whose default was ``now()`` on a
database migrated to x2f8a9b0c1d2 (queried from information_schema).

Revision ID: y3a9b0c1d2e3
Revises: x2f8a9b0c1d2
Create Date: 2026-11-05
"""

from alembic import op

revision = "y3a9b0c1d2e3"
down_revision = "x2f8a9b0c1d2"
branch_labels = None
depends_on = None

COLUMNS: tuple[tuple[str, str], ...] = (
    ("games", "created_at"),
    ("games", "updated_at"),
    ("link_codes", "created_at"),
    ("map_snapshots", "created_at"),
    ("password_reset_tokens", "created_at"),
    ("players", "created_at"),
    ("spectators", "joined_at"),
    ("tournament_games", "created_at"),
    ("tournament_players", "created_at"),
    ("tournaments", "created_at"),
    ("tournaments", "updated_at"),
)


def upgrade() -> None:
    for table, column in COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT timezone('UTC', now())")


def downgrade() -> None:
    for table, column in COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT now()")
