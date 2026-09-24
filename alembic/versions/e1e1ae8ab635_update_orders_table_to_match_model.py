"""update_orders_table_to_match_model

Revision ID: e1e1ae8ab635
Revises: bf605311f906
Create Date: 2025-10-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision: str = 'e1e1ae8ab635'
down_revision: Union[str, Sequence[str], None] = 'bf605311f906'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update orders table to match OrderModel schema."""
    # Drop old indexes first
    op.execute("DROP INDEX IF EXISTS ix_orders_player_id_turn")
    op.execute("DROP INDEX IF EXISTS ix_orders_player_id")
    op.execute("DROP INDEX IF EXISTS ix_orders_order_text")
    op.execute("DROP INDEX IF EXISTS ix_orders_turn")
    op.execute("DROP INDEX IF EXISTS ix_orders_turn_created")
    op.execute("DROP INDEX IF EXISTS ix_orders_player_created")
    
    # Drop old foreign key constraint
    try:
        op.drop_constraint('orders_player_id_fkey', 'orders', type_='foreignkey')
    except:
        pass
    
    # Drop old columns
    op.drop_column('orders', 'player_id')
    op.drop_column('orders', 'order_text')
    op.drop_column('orders', 'turn')
    
    # Add new columns
    op.add_column('orders', sa.Column('game_id', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('power_name', sa.String(20), nullable=True))
    op.add_column('orders', sa.Column('order_type', sa.String(20), nullable=True))
    op.add_column('orders', sa.Column('unit_type', sa.String(1), nullable=True))
    op.add_column('orders', sa.Column('unit_province', sa.String(20), nullable=True))
    op.add_column('orders', sa.Column('target_province', sa.String(20), nullable=True))
    op.add_column('orders', sa.Column('supported_unit_type', sa.String(1), nullable=True))
    op.add_column('orders', sa.Column('supported_unit_province', sa.String(20), nullable=True))
    op.add_column('orders', sa.Column('supported_target', sa.String(20), nullable=True))
    op.add_column('orders', sa.Column('convoyed_unit_type', sa.String(1), nullable=True))
    op.add_column('orders', sa.Column('convoyed_unit_province', sa.String(20), nullable=True))
    op.add_column('orders', sa.Column('convoyed_target', sa.String(20), nullable=True))
    op.add_column('orders', sa.Column('convoy_chain', JSON, nullable=True))
    op.add_column('orders', sa.Column('build_type', sa.String(1), nullable=True))
    op.add_column('orders', sa.Column('build_province', sa.String(20), nullable=True))
    op.add_column('orders', sa.Column('build_coast', sa.String(10), nullable=True))
    op.add_column('orders', sa.Column('destroy_unit_type', sa.String(1), nullable=True))
    op.add_column('orders', sa.Column('destroy_unit_province', sa.String(20), nullable=True))
    op.add_column('orders', sa.Column('status', sa.String(20), nullable=True, server_default='pending'))
    op.add_column('orders', sa.Column('failure_reason', sa.Text(), nullable=True))
    op.add_column('orders', sa.Column('phase', sa.String(20), nullable=True))
    op.add_column('orders', sa.Column('turn_number', sa.Integer(), nullable=True))
    
    # For existing rows, set defaults - but since this is test DB, they'll be empty
    # Set nullable=False after populating
    op.execute("UPDATE orders SET game_id = 1, power_name = 'UNKNOWN', order_type = 'hold', unit_type = 'A', unit_province = 'NONE', phase = 'Movement', turn_number = 0 WHERE game_id IS NULL")
    
    # Now make required columns NOT NULL
    op.alter_column('orders', 'game_id', nullable=False)
    op.alter_column('orders', 'power_name', nullable=False)
    op.alter_column('orders', 'order_type', nullable=False)
    op.alter_column('orders', 'unit_type', nullable=False)
    op.alter_column('orders', 'unit_province', nullable=False)
    op.alter_column('orders', 'phase', nullable=False)
    op.alter_column('orders', 'turn_number', nullable=False)
    
    # Add foreign key constraint
    op.create_foreign_key('orders_game_id_fkey', 'orders', 'games', ['game_id'], ['id'], ondelete='CASCADE')
    
    # Add check constraints
    op.create_check_constraint('ck_order_unit_type', 'orders', "unit_type IN ('A', 'F')")
    op.create_check_constraint('ck_order_type', 'orders', "order_type IN ('move', 'hold', 'support', 'convoy', 'retreat', 'build', 'destroy')")
    op.create_check_constraint('ck_order_status', 'orders', "status IN ('pending', 'submitted', 'success', 'failed', 'bounced')")
    
    # Add indexes (check if they exist first)
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_game_turn ON orders (game_id, turn_number)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_created_at ON orders (created_at)")


def downgrade() -> None:
    """Revert orders table to old schema."""
    # Drop new constraints and indexes
    op.drop_constraint('ck_order_status', 'orders', type_='check')
    op.drop_constraint('ck_order_type', 'orders', type_='check')
    op.drop_constraint('ck_order_unit_type', 'orders', type_='check')
    op.drop_index('ix_orders_game_turn', table_name='orders')
    op.drop_constraint('orders_game_id_fkey', 'orders', type_='foreignkey')
    
    # Drop new columns
    op.drop_column('orders', 'turn_number')
    op.drop_column('orders', 'phase')
    op.drop_column('orders', 'failure_reason')
    op.drop_column('orders', 'status')
    op.drop_column('orders', 'destroy_unit_province')
    op.drop_column('orders', 'destroy_unit_type')
    op.drop_column('orders', 'build_coast')
    op.drop_column('orders', 'build_province')
    op.drop_column('orders', 'build_type')
    op.drop_column('orders', 'convoy_chain')
    op.drop_column('orders', 'convoyed_target')
    op.drop_column('orders', 'convoyed_unit_province')
    op.drop_column('orders', 'convoyed_unit_type')
    op.drop_column('orders', 'supported_target')
    op.drop_column('orders', 'supported_unit_province')
    op.drop_column('orders', 'supported_unit_type')
    op.drop_column('orders', 'target_province')
    op.drop_column('orders', 'unit_province')
    op.drop_column('orders', 'unit_type')
    op.drop_column('orders', 'order_type')
    op.drop_column('orders', 'power_name')
    op.drop_column('orders', 'game_id')
    
    # Re-add old columns
    op.add_column('orders', sa.Column('turn', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('order_text', sa.String(), nullable=True))
    op.add_column('orders', sa.Column('player_id', sa.Integer(), nullable=True))
    op.alter_column('orders', 'player_id', nullable=False)
    op.alter_column('orders', 'order_text', nullable=False)
    op.alter_column('orders', 'turn', nullable=False)
    
    # Re-add foreign key
    op.create_foreign_key('orders_player_id_fkey', 'orders', 'players', ['player_id'], ['id'])
    
    # Re-add indexes
    op.create_index('ix_orders_player_id_turn', 'orders', ['player_id', 'turn'])
    op.create_index('ix_orders_player_id', 'orders', ['player_id'])
