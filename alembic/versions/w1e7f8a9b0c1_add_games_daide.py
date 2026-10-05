"""Add games.daide (the game was created by the DAIDE listener)

A DAIDE game's seats are the listener's live connections, held in memory, not
``players`` rows. The full-table rule (a turn is processed only when every
power is seated or a dummy) cannot see them, so a DAIDE game is exempt from it
and this column says which games those are. Existing games are not DAIDE games:
none can be told apart after the fact, and the listener creates a fresh game
after every restart anyway.

Revision ID: w1e7f8a9b0c1
Revises: v0d6e7f8a9b0
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa

revision = "w1e7f8a9b0c1"
down_revision = "v0d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column("daide", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("games", "daide")
