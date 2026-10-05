"""One game per Telegram group: a partial unique index on games.channel_id

A group (``games.channel_id``) belongs to at most one game, so a command typed
in the group can tell which game it is about. Before this, linking a second
game to a group left both linked. Any such duplicates are resolved first,
deterministically: the game with the highest ``id`` (the newest) keeps the
group, the others are unlinked (``channel_id`` and ``channel_settings``
cleared), exactly as ``/linkgroup`` now moves a link.

Revision ID: v0d6e7f8a9b0
Revises: u9c5d6e7f8a9
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa

revision = "v0d6e7f8a9b0"
down_revision = "u9c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE games SET channel_id = NULL, channel_settings = NULL
        WHERE channel_id IS NOT NULL
          AND id < (SELECT MAX(g2.id) FROM games g2 WHERE g2.channel_id = games.channel_id)
        """
    )
    op.create_index(
        "uq_games_channel_id",
        "games",
        ["channel_id"],
        unique=True,
        postgresql_where=sa.text("channel_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_games_channel_id", table_name="games")
