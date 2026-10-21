"""Add games.reminded_deadline (the deadline whose 10-minute reminder was sent)

The reminder used to be tracked in an in-memory dict in the API process, so a
restart or deploy inside the 10-minute window sent it again, and each uvicorn
worker could send its own. The column holds the deadline value the reminder was
sent for (naive UTC, like ``games.deadline``); a conditional UPDATE claims it,
so exactly one sender wins. Existing games start with NULL: a game already
inside its window at upgrade time may be reminded once more, as before.

Revision ID: x2f8a9b0c1d2
Revises: w1e7f8a9b0c1
Create Date: 2026-10-21
"""

from alembic import op
import sqlalchemy as sa

revision = "x2f8a9b0c1d2"
down_revision = "w1e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("reminded_deadline", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "reminded_deadline")
