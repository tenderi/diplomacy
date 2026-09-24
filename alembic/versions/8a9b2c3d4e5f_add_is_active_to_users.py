"""add_is_active_to_users

Revision ID: 8a9b2c3d4e5f
Revises: 1d10d8031457
Create Date: 2025-11-03 16:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a9b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '1d10d8031457'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_active, created_at, and updated_at columns to users table if they don't exist."""
    # Check if is_active column exists, add if it doesn't
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'is_active' not in columns:
        op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))
        # Set existing rows to active
        op.execute("UPDATE users SET is_active = true WHERE is_active IS NULL")
        # Make column NOT NULL after setting defaults
        op.alter_column('users', 'is_active', nullable=False, server_default='true')
    
    if 'created_at' not in columns:
        op.add_column('users', sa.Column('created_at', sa.DateTime(), nullable=True))
        # Set a default timestamp for existing rows
        op.execute("UPDATE users SET created_at = NOW() WHERE created_at IS NULL")
        op.alter_column('users', 'created_at', nullable=False)
    
    if 'updated_at' not in columns:
        op.add_column('users', sa.Column('updated_at', sa.DateTime(), nullable=True))
        # Set a default timestamp for existing rows
        op.execute("UPDATE users SET updated_at = NOW() WHERE updated_at IS NULL")
        op.alter_column('users', 'updated_at', nullable=False)


def downgrade() -> None:
    """Remove is_active, created_at, and updated_at columns from users table."""
    # Check if columns exist before dropping
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'updated_at' in columns:
        op.drop_column('users', 'updated_at')
    if 'created_at' in columns:
        op.drop_column('users', 'created_at')
    if 'is_active' in columns:
        op.drop_column('users', 'is_active')

