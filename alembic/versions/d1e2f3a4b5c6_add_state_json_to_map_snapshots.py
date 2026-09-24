"""PR5: add map_snapshots.state_json for real restore support

Snapshots previously stored only the view-shaped ``units``/``supply_centers``, which
``engine.serialization.state_from_dict`` cannot parse -- so ``POST
/games/{id}/restore/{snapshot_id}`` was a no-op stub. This adds a nullable JSON column
holding the full serialized ``GameState`` (``state_to_dict``) captured at snapshot
time, so a snapshot taken after this migration can be restored directly. Purely
additive: existing rows get NULL and keep working for ``/history``/``/replay``, which
never read this column; restoring a pre-migration snapshot now fails loudly (409)
instead of silently doing nothing.

Revision ID: d1e2f3a4b5c6
Revises: c3d4e5f6a7b9
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa

revision = "d1e2f3a4b5c6"
down_revision = "c3d4e5f6a7b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("map_snapshots", sa.Column("state_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("map_snapshots", "state_json")
