"""M7: add games.order_history for the per-turn order-history endpoint

The new engine keeps a game's state as a single ``GameState`` snapshot and clears
pending orders when a turn is processed, so ``GET /games/{id}/orders/history`` had
nothing to return. This adds a nullable JSON column that ``process_turn`` appends the
submitted orders to, keyed by turn: ``{turn: {power: [order_str]}}``.

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
Create Date: 2026-07-27
"""

from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b9"
down_revision = "b2c3d4e5f6a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("order_history", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "order_history")
