"""merge channel analytics and is_active deadline

Revision ID: 9ee373e5cc74
Revises: 9f8e7d6c5b4a, f8a9b7c6d5e4
Create Date: 2026-02-24 14:59:55.490578

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ee373e5cc74'
down_revision: Union[str, Sequence[str], None] = ('9f8e7d6c5b4a', 'f8a9b7c6d5e4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
