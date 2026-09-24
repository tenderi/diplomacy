"""Add games.dummy_powers and games.created_by_user_id (W9)

``dummy_powers`` is a JSON list of power names played by civil disorder: no
one may join them, nobody waits on their orders, and they are not counted in
draw-vote quorum or deadline-proposal majorities. The engine already plays a
power that submits nothing by the civil-disorder rules (hold; disband when a
retreat or removal is owed), so no game logic changes. Null or ``[]`` means
none.

``created_by_user_id`` records who created the game (null for games created
by the waiting list, the demo seeder, or before this column existed). The
creator may change the dummy set later (W9) and, with W8, a game's password.
``ON DELETE SET NULL``: deleting a user must not delete or block their games.

Revision ID: k9e5f6a7b8c9
Revises: j8d4e5f6a7b8
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa

revision = "k9e5f6a7b8c9"
down_revision = "j8d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("dummy_powers", sa.JSON(), nullable=True))
    op.add_column("games", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_games_created_by_user_id_users",
        "games",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_games_created_by_user_id_users", "games", type_="foreignkey")
    op.drop_column("games", "created_by_user_id")
    op.drop_column("games", "dummy_powers")
