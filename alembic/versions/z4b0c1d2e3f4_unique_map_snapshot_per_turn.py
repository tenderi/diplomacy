"""One map_snapshots row per (game_id, turn_number)

A processed turn's snapshot used to be written in a transaction of its own,
after the turn, under a re-read ``current_turn``, and ``POST
/games/{id}/snapshot`` added a row every call: a turn could get two rows, and
``/history/{turn}`` read whichever Postgres returned first. Duplicates already
present are collapsed to the newest row (highest id) before the constraint is
added; writers now upsert (``persistence.database.upsert_map_snapshot``).

Revision ID: z4b0c1d2e3f4
Revises: y3a9b0c1d2e3
Create Date: 2026-11-10
"""

from alembic import op

revision = "z4b0c1d2e3f4"
down_revision = "y3a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM map_snapshots older USING map_snapshots newer "
        "WHERE older.game_id = newer.game_id AND older.turn_number = newer.turn_number "
        "AND older.id < newer.id"
    )
    op.create_unique_constraint("uq_map_snapshots_game_turn", "map_snapshots", ["game_id", "turn_number"])


def downgrade() -> None:
    op.drop_constraint("uq_map_snapshots_game_turn", "map_snapshots", type_="unique")
