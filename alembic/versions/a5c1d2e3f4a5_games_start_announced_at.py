"""Add games.start_announced_at (the game-started DM was sent)

Claimed by a conditional UPDATE so exactly one request announces the start of a
game, however many fill the table at once. Existing games start NULL; the
announcement only fires for a game still on turn 0.

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


def upgrade() -> None:
    op.add_column("games", sa.Column("start_announced_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "start_announced_at")
