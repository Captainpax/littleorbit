"""Align RC14 indexes with the query model.

Revision ID: 0022
Revises: 0021
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove a redundant index covered by the pending-couple index."""

    op.execute("DROP INDEX IF EXISTS ix_relationship_start_proposals_couple_id")


def downgrade() -> None:
    """Restore the previous non-unique relationship-proposal index."""

    op.create_index(
        "ix_relationship_start_proposals_couple_id",
        "relationship_start_proposals",
        ["couple_id"],
    )
