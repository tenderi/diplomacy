"""Add games.start_announced_at (the game-started DM was sent)

Claimed by a conditional UPDATE so exactly one request announces the start of a
game, however many fill the table at once. Games that have already
started are backfilled (BACKFILL_STARTED) so a replace or dummy toggle in one
never claims the announcement; only genuinely unfilled lobby games stay NULL.

Revision ID: a5c1d2e3f4a5
Revises: z4b0c1d2e3f4
Create Date: 2026-11-11
"""

from alembic import op
import sqlalchemy as sa

revision = "a5c1d2e3f4a5"
down_revision = "z4b0c1d2e3f4"
branch_labels = None
depends_on = None


# Started = the code's own definition (``seats_filled`` / ``require_started``): a
# turn has run, the game is over, it is DAIDE-run, or every one of the seven powers
# has a seat row or is a dummy.
BACKFILL_STARTED = """
UPDATE games g SET start_announced_at = now() AT TIME ZONE 'UTC'
WHERE start_announced_at IS NULL AND (
    current_turn > 0 OR status = 'completed' OR daide
    OR (
        SELECT count(*) FROM (
            SELECT upper(power_name) AS p FROM players WHERE game_id = g.id
            UNION
            SELECT upper(x) FROM json_array_elements_text(
                CASE WHEN json_typeof(g.dummy_powers) = 'array' THEN g.dummy_powers ELSE '[]'::json END
            ) AS x
        ) AS covered
    ) >= 7
)
"""


def upgrade() -> None:
    op.add_column("games", sa.Column("start_announced_at", sa.DateTime(), nullable=True))
    op.execute(BACKFILL_STARTED)


def downgrade() -> None:
    op.drop_column("games", "start_announced_at")
