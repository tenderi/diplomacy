"""Add games.random_powers (powers assigned at random on join)

Chosen when a game is created. In a random-powers game a joining player does
not pick a power: the server seats them in a random open one. Existing games
keep letting players choose, which is how they have always behaved.

Revision ID: t8b4c5d6e7f8
Revises: s7a3b4c5d6e7
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa

revision = "t8b4c5d6e7f8"
down_revision = "s7a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column("random_powers", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("games", "random_powers")
