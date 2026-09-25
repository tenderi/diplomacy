"""Add feedback (Track AT)

Player reports from the bot's ``/feedback`` and the web's feedback page.

Revision ID: p4d0e1f2a3b4
Revises: o3c9d0e1f2a3
Create Date: 2026-09-25
"""

from alembic import op
import sqlalchemy as sa

revision = "p4d0e1f2a3b4"
down_revision = "o3c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("game_id", sa.String(50), nullable=True),
        sa.Column("phase_code", sa.String(10), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_feedback_user_created", "feedback", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_feedback_user_created", table_name="feedback")
    op.drop_table("feedback")
