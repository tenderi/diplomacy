"""Drop channel_analytics (Track AQ)

Nothing has read or written it since Track AH (v3.0.13): its only writer was bot-side
posting code that never ran in production, its only reader the removed admin dashboard.
Checked empty in production (0 rows) on 2026-09-25 before this was written. The
downgrade recreates the empty table exactly as ``f8a9b7c6d5e4`` created it.

Revision ID: n2b8c9d0e1f2
Revises: m1a7b8c9d0e1
Create Date: 2026-09-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "n2b8c9d0e1f2"
down_revision = "m1a7b8c9d0e1"
branch_labels = None
depends_on = None

_INDEXES = {
    "ix_channel_analytics_game_channel": ["game_id", "channel_id"],
    "ix_channel_analytics_event_type": ["event_type"],
    "ix_channel_analytics_created_at": ["created_at"],
    "ix_channel_analytics_user": ["user_id"],
}


def upgrade() -> None:
    # IF EXISTS: a database built by the schema autoupdater rather than migrations may
    # never have had it.
    op.execute("DROP TABLE IF EXISTS channel_analytics")


def downgrade() -> None:
    op.create_table(
        "channel_analytics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_subtype", sa.String(50), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("power", sa.String(20), nullable=True),
        sa.Column("event_data", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in _INDEXES.items():
        op.create_index(name, "channel_analytics", columns)
