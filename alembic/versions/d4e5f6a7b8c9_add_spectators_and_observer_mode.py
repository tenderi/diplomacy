"""Add spectators table and observer_mode to games

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2025-03-02

- spectators: game_id, user_id, joined_at
- games.observer_mode: boolean, allow non-players to spectate
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add observer_mode to games if not present (optional; some DBs may have games already)
    try:
        op.add_column(
            'games',
            sa.Column('observer_mode', sa.Boolean(), nullable=True, server_default='false'),
        )
    except Exception:
        pass  # Column may already exist

    op.create_table(
        'spectators',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('game_id', 'user_id', name='uq_spectator_game_user'),
    )
    op.create_index('ix_spectators_game', 'spectators', ['game_id'])


def downgrade() -> None:
    op.drop_index('ix_spectators_game', table_name='spectators')
    op.drop_table('spectators')
    try:
        op.drop_column('games', 'observer_mode')
    except Exception:
        pass
