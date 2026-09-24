"""Track W: games.phase_length_seconds, games.resolution_history, messages.phase_code

Three gaps the pre-deletion audit of ``old_implementation/`` turned up (recorded
in commit ``cfa8d93``, never merged; the audit's own "Track K" numbering
collides with this repo's later, unrelated Track K and is not reused here):

``games.phase_length_seconds``
    A convenience for ``POST /games/{id}/deadline``: pass it with no explicit
    ``deadline`` and the route arms one ``phase_length_seconds`` out. Nothing
    re-arms a deadline automatically after a turn is processed -- Track N
    already decided deadlines exist only when set explicitly, and this column
    does not revisit that. NULL = use the 24 h default for that one call.

``games.resolution_history``
    ``last_resolution`` is overwritten every turn, so the outcomes of turn 3 were
    gone as soon as turn 4 ran -- ``order_history`` kept what was ordered but not
    what happened. Same ``{turn: ...}`` shape as ``order_history``.

``messages.phase_code``
    The old ``Message`` carried the phase it was sent in; the port kept only a
    timestamp. Nullable because existing rows have no way to recover it.

Revision ID: i7c3d4e5f6a7
Revises: h6b2c3d4e5f6
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa

revision = "i7c3d4e5f6a7"
down_revision = "h6b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("phase_length_seconds", sa.Integer(), nullable=True))
    op.add_column("games", sa.Column("resolution_history", sa.JSON(), nullable=True))
    op.add_column("messages", sa.Column("phase_code", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "phase_code")
    op.drop_column("games", "resolution_history")
    op.drop_column("games", "phase_length_seconds")
