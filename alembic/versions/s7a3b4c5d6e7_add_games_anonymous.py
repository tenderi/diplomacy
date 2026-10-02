"""Add games.anonymous (anonymous or public player names)

Chosen when a game is created. An anonymous game names players only by their
power in every announcement and relayed message; a public one shows the
player's nickname next to the power. Existing games stay public, which is how they
have always behaved.

Revision ID: s7a3b4c5d6e7
Revises: r6f2a3b4c5d6
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa

revision = "s7a3b4c5d6e7"
down_revision = "r6f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column("anonymous", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("games", "anonymous")
