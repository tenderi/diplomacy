"""add_units_and_supply_centers_tables

Revision ID: 03c27dc1b89b
Revises: e1e1ae8ab635
Create Date: 2025-10-31 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision: str = '03c27dc1b89b'
down_revision: Union[str, Sequence[str], None] = 'e1e1ae8ab635'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add units and supply_centers tables to match models."""
    # Create units table
    op.create_table('units',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('power_name', sa.String(20), nullable=False),
        sa.Column('unit_type', sa.String(1), nullable=False),
        sa.Column('province', sa.String(20), nullable=False),
        sa.Column('is_dislodged', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('dislodged_by', sa.String(20), nullable=True),
        sa.Column('can_retreat', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('retreat_options', JSON, nullable=True, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('game_id', 'province', name='uq_game_province'),
        sa.CheckConstraint("unit_type IN ('A', 'F')", name='ck_unit_type')
    )
    op.create_index('ix_units_game', 'units', ['game_id'])
    
    # Create supply_centers table
    op.create_table('supply_centers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('province', sa.String(20), nullable=False),
        sa.Column('controlling_power', sa.String(20), nullable=True),
        sa.Column('is_home_supply_center', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('home_power', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('game_id', 'province', name='uq_game_supply_province')
    )
    op.create_index('ix_supply_centers_game', 'supply_centers', ['game_id'])


def downgrade() -> None:
    """Remove units and supply_centers tables."""
    op.drop_index('ix_supply_centers_game', table_name='supply_centers')
    op.drop_table('supply_centers')
    op.drop_index('ix_units_game', table_name='units')
    op.drop_table('units')
