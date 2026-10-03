"""Add messages.anonymous (rumours: broadcasts that name no sender)

A player may send a broadcast anonymously, to spread a rumour. The sender is
still stored in ``sender_user_id`` for the record, but no read path shows it to
anyone but the sender. Every existing message was signed.

Revision ID: u9c5d6e7f8a9
Revises: t8b4c5d6e7f8
Create Date: 2026-10-03
"""

from alembic import op
import sqlalchemy as sa

revision = "u9c5d6e7f8a9"
down_revision = "t8b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("anonymous", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("messages", "anonymous")
