"""M7: add games.last_resolution for resolution-map rendering

The resolution map (``POST /games/{id}/generate_map/resolution``) draws each
adjudicated order's arrow coloured by its result. Adjudication happens at
``process_turn``, after which the pending orders are cleared, so the resolution
would otherwise be lost. This adds a nullable JSON column holding the most recent
``engine.serialization.resolution_to_dict`` output purely for that render.

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-07-27
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("last_resolution", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "last_resolution")
