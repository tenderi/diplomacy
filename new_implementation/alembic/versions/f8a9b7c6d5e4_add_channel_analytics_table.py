"""Add channel_analytics table for tracking engagement metrics

Revision ID: f8a9b7c6d5e4
Revises: add_channel_fields
Create Date: 2025-01-30

This migration adds the channel_analytics table for tracking:
- Message posting events (maps, broadcasts, notifications, etc.)
- Player activity (order submissions, message reads, voting)
- Engagement metrics (response times, participation rates)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = 'f8a9b7c6d5e4'
down_revision = 'add_channel_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create channel_analytics table."""
    op.create_table(
        'channel_analytics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.String(255), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_subtype', sa.String(50), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('power', sa.String(20), nullable=True),
        sa.Column('metadata', JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for efficient querying
    op.create_index('ix_channel_analytics_game_channel', 'channel_analytics', ['game_id', 'channel_id'])
    op.create_index('ix_channel_analytics_event_type', 'channel_analytics', ['event_type'])
    op.create_index('ix_channel_analytics_created_at', 'channel_analytics', ['created_at'])
    op.create_index('ix_channel_analytics_user', 'channel_analytics', ['user_id'])


def downgrade() -> None:
    """Drop channel_analytics table."""
    op.drop_index('ix_channel_analytics_user', table_name='channel_analytics')
    op.drop_index('ix_channel_analytics_created_at', table_name='channel_analytics')
    op.drop_index('ix_channel_analytics_event_type', table_name='channel_analytics')
    op.drop_index('ix_channel_analytics_game_channel', table_name='channel_analytics')
    op.drop_table('channel_analytics')
