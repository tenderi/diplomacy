"""add_missing_player_model_columns

Revision ID: bf605311f906
Revises: bd48b54f9c5f
Create Date: 2025-10-31 11:09:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision: str = 'bf605311f906'
down_revision: Union[str, Sequence[str], None] = 'bd48b54f9c5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing columns to players table to match PlayerModel spec."""
    # Add is_eliminated column
    op.add_column('players', sa.Column('is_eliminated', sa.Boolean(), nullable=True, server_default='false'))
    op.alter_column('players', 'is_eliminated', nullable=False)
    
    # Add JSON columns for supply centers
    op.add_column('players', sa.Column('home_supply_centers', JSON, nullable=True, server_default='[]'))
    op.add_column('players', sa.Column('controlled_supply_centers', JSON, nullable=True, server_default='[]'))
    
    # Add orders_submitted boolean
    op.add_column('players', sa.Column('orders_submitted', sa.Boolean(), nullable=True, server_default='false'))
    op.alter_column('players', 'orders_submitted', nullable=False)
    
    # Add last_order_time timestamp (nullable)
    op.add_column('players', sa.Column('last_order_time', sa.DateTime(), nullable=True))
    
    # Add created_at timestamp
    op.add_column('players', sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()))
    op.alter_column('players', 'created_at', nullable=False)


def downgrade() -> None:
    """Remove added columns."""
    op.drop_column('players', 'created_at')
    op.drop_column('players', 'last_order_time')
    op.drop_column('players', 'orders_submitted')
    op.drop_column('players', 'controlled_supply_centers')
    op.drop_column('players', 'home_supply_centers')
    op.drop_column('players', 'is_eliminated')
