"""Add games.deadline_schedule (weekly deadline schedules)

A JSON weekly schedule such as Mon/Wed/Fri 16:00 in a named timezone. While
set, every phase's deadline is armed to its next slot. Null = no schedule.

Revision ID: q5e1f2a3b4c5
Revises: p4d0e1f2a3b4
Create Date: 2026-09-25
"""

from alembic import op
import sqlalchemy as sa

revision = "q5e1f2a3b4c5"
down_revision = "p4d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("deadline_schedule", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "deadline_schedule")
