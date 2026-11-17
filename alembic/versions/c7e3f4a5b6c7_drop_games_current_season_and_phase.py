"""Drop games.current_season and games.current_phase

Both copied ``state_json``'s ``season`` and ``phase_type`` (capitalized) on
every save, and the only reader was the ``GET /games`` listing, which now
derives the same values from ``state_json`` (issue #464). The downgrade
re-adds them and backfills them from ``state_json``.

Revision ID: c7e3f4a5b6c7
Revises: b6d2e3f4a5b6
Create Date: 2026-11-17
"""

import sqlalchemy as sa
from alembic import op

revision = "c7e3f4a5b6c7"
down_revision = "b6d2e3f4a5b6"
branch_labels = None
depends_on = None

BACKFILL = (
    "UPDATE games SET "
    "current_season = initcap(coalesce(state_json->>'season', 'SPRING')), "
    "current_phase = initcap(coalesce(state_json->>'phase_type', 'MOVEMENT'))"
)


def upgrade() -> None:
    op.drop_column("games", "current_phase")
    op.drop_column("games", "current_season")


def downgrade() -> None:
    op.add_column("games", sa.Column("current_season", sa.String(10), nullable=False, server_default="Spring"))
    op.add_column("games", sa.Column("current_phase", sa.String(20), nullable=False, server_default="Movement"))
    op.execute(BACKFILL)
