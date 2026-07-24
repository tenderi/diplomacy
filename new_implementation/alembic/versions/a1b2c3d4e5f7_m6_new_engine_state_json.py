"""M6: new-engine state_json + pending_orders on games; wipe legacy game data

The engine rewrite stores a game's whole state as a single serialized ``GameState``
(``games.state_json``) plus its pending orders (``games.pending_orders``), replacing
the legacy relational units/orders/supply_centers storage. Game data is explicitly
disposable (no backwards compatibility required), so this migration wipes all
game-related rows; users/auth/link-codes are kept.

Revision ID: a1b2c3d4e5f7
Revises: f6a7b8c9d0e1
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f7"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


# Legacy game-scoped tables cleared on upgrade (order respects FKs). Only tables
# that actually exist are touched.
_GAME_TABLES = [
    "turn_history",
    "map_snapshots",
    "spectators",
    "orders",
    "units",
    "supply_centers",
    "messages",
    "players",
    "games",
]


def upgrade() -> None:
    op.add_column("games", sa.Column("state_json", sa.JSON(), nullable=True))
    op.add_column("games", sa.Column("pending_orders", sa.JSON(), nullable=True))

    # Wipe disposable game data (keep users/auth). Use TRUNCATE ... CASCADE so we do
    # not have to enumerate every FK edge; skip tables that don't exist.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    to_wipe = [t for t in _GAME_TABLES if t in existing]
    if to_wipe:
        op.execute(f"TRUNCATE TABLE {', '.join(to_wipe)} RESTART IDENTITY CASCADE")


def downgrade() -> None:
    op.drop_column("games", "pending_orders")
    op.drop_column("games", "state_json")
