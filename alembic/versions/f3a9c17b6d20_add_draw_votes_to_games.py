"""D3/C3: add games.draw_votes for the draw-vote mechanism

Adds a nullable JSON column storing per-phase draw-vote yes-votes,
``{power: "yes"}`` -- absence of a power means no/not-voted, so only yes-votes
need to be recorded. Mirrors ``pending_orders``: cleared every processed turn
(a draw vote is scoped to the current phase, not a standing position), via the
same ``GameRepo`` write path. Purely additive: existing rows get NULL, read
back as ``{}`` by ``GameRepo.get_draw_votes``.

Revision ID: f3a9c17b6d20
Revises: d1e2f3a4b5c6
Create Date: 2026-07-29
"""

from alembic import op
import sqlalchemy as sa

revision = "f3a9c17b6d20"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("draw_votes", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "draw_votes")
