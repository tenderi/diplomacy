"""G5: add the waiting_list table

Moves the automatic-matching queue out of ``telegram_bot/games.py``'s in-memory
``WAITING_LIST`` global and into Postgres. The bot is restarted on every deploy,
so a partially filled queue vanished silently and the queued players were never
told; and holding game state in the bot violates the thin-client boundary the
rest of the bot observes.

``telegram_id`` is UNIQUE so a repeated ``/wait`` cannot claim two slots.
``joined_at`` is indexed because every read is "the N longest-waiting entries"
(FIFO), which is also what lets an 8th queued player be held for the next game
instead of dropped.

Naive ``TIMESTAMP`` for ``joined_at``, matching every other datetime column in
this schema -- see ``persistence.database.utcnow_naive``, which returns naive UTC
on purpose because handing Postgres a tz-aware value makes it store a shifted
value on non-UTC hosts.

Revision ID: g5a1c2d3e4f5
Revises: f3a9c17b6d20
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa

revision = "g5a1c2d3e4f5"
down_revision = "f3a9c17b6d20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "waiting_list",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("telegram_id", name="uq_waiting_list_telegram_id"),
    )
    op.create_index("ix_waiting_list_joined_at", "waiting_list", ["joined_at"])


def downgrade() -> None:
    op.drop_index("ix_waiting_list_joined_at", table_name="waiting_list")
    op.drop_table("waiting_list")
