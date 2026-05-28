"""Add turn_history table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-28

TurnHistoryModel (src/engine/database.py) uses __tablename__ = 'turn_history'
with a richer schema (turn_number, year, season, phase, phase_code,
units_before/after, supply_centers_before/after). The initial Alembic
migration ac6a8bd4ac64 created a different legacy table named
'game_history' that no current code uses. Local DBs picked up the
'turn_history' schema via Base.metadata.create_all() on server startup
so the drift went unnoticed until CI started running alembic against
a clean container and `delete_all_game_history()` failed with
"relation 'turn_history' does not exist".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'turn_history' in inspector.get_table_names():
        return

    op.create_table(
        'turn_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'game_id',
            sa.Integer(),
            sa.ForeignKey('games.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('season', sa.String(length=10), nullable=False),
        sa.Column('phase', sa.String(length=20), nullable=False),
        sa.Column('phase_code', sa.String(length=10), nullable=False),
        sa.Column('units_before', sa.JSON(), nullable=True),
        sa.Column('units_after', sa.JSON(), nullable=True),
        sa.Column('supply_centers_before', sa.JSON(), nullable=True),
        sa.Column('supply_centers_after', sa.JSON(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.create_index(
        'ix_turn_history_game_id', 'turn_history', ['game_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_turn_history_game_id', table_name='turn_history')
    op.drop_table('turn_history')
