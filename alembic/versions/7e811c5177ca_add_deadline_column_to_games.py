"""add_deadline_column_to_games

Revision ID: 7e811c5177ca
Revises: 1d10d8031457
Create Date: 2025-11-03 16:32:46.134396

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e811c5177ca'
down_revision: Union[str, Sequence[str], None] = '1d10d8031457'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add deadline column to games table."""
    # Check if column already exists before adding
    from alembic import context
    from sqlalchemy import inspect
    
    conn = context.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('games')]
    
    if 'deadline' not in columns:
        op.add_column('games', sa.Column('deadline', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove deadline column from games table."""
    from alembic import context
    from sqlalchemy import inspect
    
    conn = context.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('games')]
    
    if 'deadline' in columns:
        op.drop_column('games', 'deadline')
