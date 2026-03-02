"""Add tournament tables for bracket/tournament organization

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-03-02

Tables: tournaments, tournament_games, tournament_players
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tournaments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('bracket_type', sa.String(50), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'tournament_games',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tournament_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('round_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('bracket_position', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tournament_id', 'game_id', name='uq_tournament_game'),
    )
    op.create_index('ix_tournament_games_tournament', 'tournament_games', ['tournament_id'])

    op.create_table(
        'tournament_players',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tournament_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('seed', sa.Integer(), nullable=True),
        sa.Column('final_rank', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tournament_id', 'user_id', name='uq_tournament_user'),
    )
    op.create_index('ix_tournament_players_tournament', 'tournament_players', ['tournament_id'])


def downgrade() -> None:
    op.drop_index('ix_tournament_players_tournament', table_name='tournament_players')
    op.drop_table('tournament_players')
    op.drop_index('ix_tournament_games_tournament', table_name='tournament_games')
    op.drop_table('tournament_games')
    op.drop_table('tournaments')
