"""Drop the tournament and spectator tables and games.observer_mode

4.0.0 removes tournaments and spectators (issue #461): the routes, the models
and the DAL methods are gone, and nothing reads these tables. They were empty
in production when this was written (a read-only count of each, 2026-11-16).
``games.observer_mode`` (the spectator switch) goes with them: nothing reads it.

The upgrade refuses to run if any of them holds a row, so a deployment that did
use them does not lose data silently: export or delete the rows, then upgrade.
The downgrade recreates the four tables, empty, as the previous head had them
(naive timestamps defaulting to ``timezone('UTC', now())``), and the column as false.

Revision ID: b6d2e3f4a5b6
Revises: a5c1d2e3f4a5
Create Date: 2026-11-16
"""

import sqlalchemy as sa
from alembic import op

revision = "b6d2e3f4a5b6"
down_revision = "a5c1d2e3f4a5"
branch_labels = None
depends_on = None

# Children before parents: the two link tables reference ``tournaments``.
TABLES: tuple[str, ...] = ("tournament_games", "tournament_players", "tournaments", "spectators")

UTC_NOW = sa.text("timezone('UTC', now())")


def upgrade() -> None:
    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names())
    for table in TABLES:
        if table not in existing:
            continue
        if conn.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first() is not None:  # nosec B608
            raise RuntimeError(
                f"Table {table} is not empty. 4.0.0 removes tournaments and spectators: "
                "export or delete its rows, then run the upgrade again."
            )
    for table in TABLES:
        if table in existing:
            op.drop_table(table)
    if "observer_mode" in {c["name"] for c in sa.inspect(conn).get_columns("games")}:
        op.drop_column("games", "observer_mode")


def downgrade() -> None:
    op.add_column("games", sa.Column("observer_mode", sa.Boolean(), nullable=True, server_default="false"))
    op.create_table(
        "tournaments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("bracket_type", sa.String(50), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=UTC_NOW),
        sa.Column("updated_at", sa.DateTime(), server_default=UTC_NOW),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tournament_games",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tournament_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("bracket_position", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=UTC_NOW),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tournament_id", "game_id", name="uq_tournament_game"),
    )
    op.create_index("ix_tournament_games_tournament", "tournament_games", ["tournament_id"])
    op.create_table(
        "tournament_players",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tournament_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("final_rank", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=UTC_NOW),
        sa.ForeignKeyConstraint(["tournament_id"], ["tournaments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tournament_id", "user_id", name="uq_tournament_user"),
    )
    op.create_index("ix_tournament_players_tournament", "tournament_players", ["tournament_id"])
    op.create_table(
        "spectators",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False, server_default=UTC_NOW),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "user_id", name="uq_spectator_game_user"),
    )
    op.create_index("ix_spectators_game", "spectators", ["game_id"])
