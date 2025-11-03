"""merge_is_active_and_deadline

Revision ID: 9f8e7d6c5b4a
Revises: 7e811c5177ca, 8a9b2c3d4e5f
Create Date: 2025-11-03 16:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f8e7d6c5b4a'
down_revision: Union[str, Sequence[str], None] = ('7e811c5177ca', '8a9b2c3d4e5f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration - both branches are already applied, no action needed."""
    pass


def downgrade() -> None:
    """Merge migration - no action needed for downgrade."""
    pass

