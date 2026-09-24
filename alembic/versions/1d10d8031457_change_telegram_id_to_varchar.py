"""change_telegram_id_to_varchar

Revision ID: 1d10d8031457
Revises: 66d1fe6d1762
Create Date: 2025-10-31 14:09:00.801339

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d10d8031457'
down_revision: Union[str, Sequence[str], None] = '66d1fe6d1762'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change telegram_id column from INTEGER to VARCHAR(255) to support string IDs."""
    # First, drop the unique constraint if it exists
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_telegram_id_key")
    
    # Change column type from INTEGER to VARCHAR(255)
    # Convert existing integer values to strings
    op.execute("""
        ALTER TABLE users 
        ALTER COLUMN telegram_id TYPE VARCHAR(255) 
        USING telegram_id::text
    """)
    
    # Recreate the unique constraint
    op.create_unique_constraint('uq_users_telegram_id', 'users', ['telegram_id'])


def downgrade() -> None:
    """Revert telegram_id column back to INTEGER."""
    # Drop the unique constraint
    op.drop_constraint('uq_users_telegram_id', 'users', type_='unique')
    
    # Change column type from VARCHAR(255) to INTEGER
    # Only convert values that can be converted to integers
    op.execute("""
        ALTER TABLE users 
        ALTER COLUMN telegram_id TYPE INTEGER 
        USING CASE 
            WHEN telegram_id ~ '^[0-9]+$' THEN telegram_id::integer 
            ELSE 0 
        END
    """)
    
    # Recreate the unique constraint
    op.create_unique_constraint('users_telegram_id_key', 'users', ['telegram_id'])
