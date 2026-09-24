"""Add games.auto_process and games.wait_flags (W10)

``auto_process``: when true, a turn is processed the moment every power with
something to order (civil-disorder dummies excluded, W9) has submitted and no
player has a wait flag up. Null/false keeps the old behaviour: /processturn by
hand, or a deadline.

``wait_flags``: ``{power: true}`` for players who asked the table to wait
("don't process yet, I'm still negotiating"). Cleared every time a turn is
processed. A deadline processes the turn regardless.

Revision ID: l0f6a7b8c9d0
Revises: k9e5f6a7b8c9
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa

revision = "l0f6a7b8c9d0"
down_revision = "k9e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("auto_process", sa.Boolean(), nullable=True))
    op.add_column("games", sa.Column("wait_flags", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "wait_flags")
    op.drop_column("games", "auto_process")
