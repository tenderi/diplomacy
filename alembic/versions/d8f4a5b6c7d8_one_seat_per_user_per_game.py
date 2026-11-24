"""One seat per user per game: unique players(game_id, user_id) where user_id is set

``POST /games/{id}/join`` checked "already joined?" with a plain read, then wrote
the seat in another transaction: two joins by one user at once (a double-click,
or the web and the bot together) both passed the check and seated that user in
two powers. The seat writes now re-check under the game-row lock; this index is
the backstop. A vacant seat (``user_id`` NULL) does not count.

Should a game already hold duplicates, the user keeps their earliest seat (lowest
id) and the later ones are vacated (``user_id`` set to NULL, ``is_active`` false,
as ``/quit`` leaves a seat), not deleted: the power and its row stay.

Revision ID: d8f4a5b6c7d8
Revises: c7e3f4a5b6c7
Create Date: 2026-11-24
"""

from alembic import op

revision = "d8f4a5b6c7d8"
down_revision = "c7e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE players later SET user_id = NULL, is_active = false "
        "FROM players earlier "
        "WHERE later.game_id = earlier.game_id AND later.user_id = earlier.user_id "
        "AND earlier.id < later.id"
    )
    op.create_index(
        "uq_players_game_user",
        "players",
        ["game_id", "user_id"],
        unique=True,
        postgresql_where="user_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_players_game_user", table_name="players")
