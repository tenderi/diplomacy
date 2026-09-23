"""Add games.pending_deadline_proposal for majority-vote deadline changes

Deadline changes used to be unilateral -- any single player in the game could
call POST /games/{id}/deadline and everyone else lived with it. This column
holds an in-flight proposal to change the deadline (or clear it), which
resolves once a majority of active powers (the same population as a draw
vote's quorum -- non-eliminated, with a unit) votes yes.

``pending_deadline_proposal`` shape:

    {
        "proposed_by": "FRANCE",
        "value_hours": 24.0,          # null = "clear the deadline"
        "votes": {"FRANCE": "yes"},
        "vote_deadline": "2026-...",  # null = no expiry
        "created_at": "2026-...",
    }

Nullable; null means no proposal is currently pending. Only one may be
pending per game at a time.

Revision ID: j8d4e5f6a7b8
Revises: i7c3d4e5f6a7
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa

revision = "j8d4e5f6a7b8"
down_revision = "i7c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("pending_deadline_proposal", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "pending_deadline_proposal")
