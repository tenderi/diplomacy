"""Add map_snapshots table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-28

The MapSnapshotModel (src/engine/database.py) was defined but never had
a corresponding Alembic migration. Local DBs picked it up via the
Base.metadata.create_all() schema autocreator at server startup, so the
gap went unnoticed until CI started running alembic against a clean
database and several API tests failed with
"relation 'map_snapshots' does not exist".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guard against pre-existing tables (some envs may have had it
    # auto-created by Base.metadata.create_all()).
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'map_snapshots' in inspector.get_table_names():
        return

    op.create_table(
        'map_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'game_id',
            sa.Integer(),
            sa.ForeignKey('games.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('phase_code', sa.String(length=10), nullable=False),
        sa.Column('units', sa.JSON(), nullable=False),
        sa.Column('supply_centers', sa.JSON(), nullable=False),
        sa.Column('map_image_path', sa.String(length=255), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.create_index(
        'ix_map_snapshots_game_id', 'map_snapshots', ['game_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_map_snapshots_game_id', table_name='map_snapshots')
    op.drop_table('map_snapshots')
