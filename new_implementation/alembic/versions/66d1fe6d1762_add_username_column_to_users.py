"""add_username_column_to_users

Revision ID: 66d1fe6d1762
Revises: 03c27dc1b89b
Create Date: 2025-10-31 12:32:59.620276

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66d1fe6d1762'
down_revision: Union[str, Sequence[str], None] = '03c27dc1b89b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add username column to users table."""
    op.add_column('users', sa.Column('username', sa.String(255), nullable=True))


def downgrade() -> None:
    """Remove username column from users table."""
    op.drop_column('users', 'username')
