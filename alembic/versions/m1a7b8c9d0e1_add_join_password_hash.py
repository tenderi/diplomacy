"""Add games.join_password_hash (W8: private games)

A bcrypt hash (same scheme as user passwords). Null = open game, joinable by
anyone. Non-null = /join and /replace require the password, except for the
game's creator. The hash never leaves the API: views expose only ``private``.

Revision ID: m1a7b8c9d0e1
Revises: l0f6a7b8c9d0
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa

revision = "m1a7b8c9d0e1"
down_revision = "l0f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("join_password_hash", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "join_password_hash")
