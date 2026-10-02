"""Nicknames, not real names

``users.full_name`` held whatever the bot copied from a player's Telegram profile
(first and last name -- usually a real name) or the web's optional "Full name"
field (or, when that was empty, the local part of the email). The system should
hold no real names, so the column becomes ``nickname``: optional, chosen by the
player, unique ignoring case. Every existing value is cleared -- there is no
telling which were real. The always-empty ``users.username`` (meant for the
Telegram @handle) and the waiting list's copy of the Telegram name are dropped.

Revision ID: r6f2a3b4c5d6
Revises: q5e1f2a3b4c5
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa

revision = "r6f2a3b4c5d6"
down_revision = "q5e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "full_name", new_column_name="nickname", existing_type=sa.String(255), nullable=True)
    op.execute("UPDATE users SET nickname = NULL")
    op.alter_column("users", "nickname", type_=sa.String(24), existing_nullable=True)
    op.create_index("uq_users_nickname_lower", "users", [sa.text("lower(nickname)")], unique=True)
    op.drop_column("users", "username")
    op.drop_column("waiting_list", "full_name")


def downgrade() -> None:
    # The cleared names are not restored: downgrading gives the old shape, not the old data.
    op.add_column("waiting_list", sa.Column("full_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("username", sa.String(255), nullable=True))
    op.drop_index("uq_users_nickname_lower", table_name="users")
    op.alter_column("users", "nickname", type_=sa.String(255), existing_nullable=True)
    op.execute("UPDATE users SET nickname = COALESCE(email, telegram_id, 'user ' || id)")
    op.alter_column("users", "nickname", new_column_name="full_name", nullable=False)
