"""Add channel_id and channel_settings to games table

Revision ID: add_channel_fields
Revises: latest
Create Date: 2025-01-27

This migration adds support for Telegram channel integration:
- channel_id: Telegram channel ID for channel-linked games
- channel_settings: JSON field for channel configuration
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = 'add_channel_fields'
down_revision = None  # Will be set to latest migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add channel_id and channel_settings columns to games table."""
    # Add channel_id column
    op.add_column('games', sa.Column('channel_id', sa.String(255), nullable=True))
    
    # Add channel_settings column (JSON)
    op.add_column('games', sa.Column('channel_settings', JSON, nullable=True))


def downgrade() -> None:
    """Remove channel_id and channel_settings columns from games table."""
    op.drop_column('games', 'channel_settings')
    op.drop_column('games', 'channel_id')

