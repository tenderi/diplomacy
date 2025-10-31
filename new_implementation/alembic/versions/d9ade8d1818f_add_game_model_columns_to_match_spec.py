"""add_game_model_columns_to_match_spec

Revision ID: d9ade8d1818f
Revises: 364890b0d05e
Create Date: 2025-10-31 09:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd9ade8d1818f'
down_revision: Union[str, Sequence[str], None] = '364890b0d05e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing columns to games table to match GameModel spec."""
    # Add game_id column (string, unique, nullable=False, but set default for existing rows)
    op.add_column('games', sa.Column('game_id', sa.String(50), nullable=True))
    # Set game_id to string version of id for existing rows
    op.execute("UPDATE games SET game_id = id::text WHERE game_id IS NULL")
    # Now make it NOT NULL
    op.alter_column('games', 'game_id', nullable=False)
    # Add unique constraint
    op.create_unique_constraint('uq_games_game_id', 'games', ['game_id'])
    
    # Add current_turn, current_year, current_season, current_phase, phase_code, status
    op.add_column('games', sa.Column('current_turn', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('games', sa.Column('current_year', sa.Integer(), nullable=True, server_default='1901'))
    op.add_column('games', sa.Column('current_season', sa.String(10), nullable=True, server_default='Spring'))
    op.add_column('games', sa.Column('current_phase', sa.String(20), nullable=True, server_default='Movement'))
    op.add_column('games', sa.Column('phase_code', sa.String(10), nullable=True, server_default='S1901M'))
    op.add_column('games', sa.Column('status', sa.String(20), nullable=True, server_default='active'))
    
    # Make columns NOT NULL after setting defaults
    op.alter_column('games', 'current_turn', nullable=False)
    op.alter_column('games', 'current_year', nullable=False)
    op.alter_column('games', 'current_season', nullable=False)
    op.alter_column('games', 'current_phase', nullable=False)
    op.alter_column('games', 'phase_code', nullable=False)
    op.alter_column('games', 'status', nullable=False)
    
    # Add created_at and updated_at timestamps
    op.add_column('games', sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()))
    op.add_column('games', sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()))
    op.alter_column('games', 'created_at', nullable=False)
    op.alter_column('games', 'updated_at', nullable=False)
    
    # Make state column nullable (legacy column, not used by new GameModel)
    op.alter_column('games', 'state', nullable=True)


def downgrade() -> None:
    """Remove added columns."""
    op.drop_constraint('uq_games_game_id', 'games', type_='unique')
    op.drop_column('games', 'updated_at')
    op.drop_column('games', 'created_at')
    op.drop_column('games', 'status')
    op.drop_column('games', 'phase_code')
    op.drop_column('games', 'current_phase')
    op.drop_column('games', 'current_season')
    op.drop_column('games', 'current_year')
    op.drop_column('games', 'current_turn')
    op.drop_column('games', 'game_id')
