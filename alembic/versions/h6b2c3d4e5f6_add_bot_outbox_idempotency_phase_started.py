"""Split deployment (Track J): bot_outbox, idempotency_keys, games.phase_started_at

The Telegram bot now runs on a VPS and reaches the API on the home server over
a WireGuard tunnel that can drop. Three schema additions make that survivable
without ever losing a message in either direction:

``bot_outbox``
    Every server-to-player notification is committed here before anything is
    sent. The bot pulls undelivered rows (``GET /bot/outbox``) and acks them
    once Telegram has accepted the message. Replaces the fire-and-forget
    ``requests.post`` to the bot's old port-8081 server, which dropped every
    DM the moment the bot was unreachable.

``idempotency_keys``
    The bot retries queued writes (orders, messages) until acknowledged. A
    retry of a request whose *response* was lost must not apply twice, so the
    first response is stored under the bot-supplied ``Idempotency-Key`` and
    replayed to any later request carrying the same key.

``games.phase_started_at``
    When the current phase began. The bot stamps each queued order submission
    with the time it was composed; one composed before the phase began was
    written against a board that has since been adjudicated, and is refused
    rather than silently applied to the wrong turn. Nullable: existing games
    have no value until their next phase change and skip the check until then.

All timestamps are naive UTC, matching every other datetime column here --
see ``persistence.database.utcnow_naive``.

Revision ID: h6b2c3d4e5f6
Revises: g5a1c2d3e4f5
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa

revision = "h6b2c3d4e5f6"
down_revision = "g5a1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="dm"),
        sa.Column("telegram_id", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_bot_outbox_delivered_at_id", "bot_outbox", ["delivered_at", "id"]
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_idempotency_keys_created_at", "idempotency_keys", ["created_at"]
    )

    op.add_column("games", sa.Column("phase_started_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "phase_started_at")
    op.drop_index("ix_idempotency_keys_created_at", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
    op.drop_index("ix_bot_outbox_delivered_at_id", table_name="bot_outbox")
    op.drop_table("bot_outbox")
