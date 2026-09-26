"""Shorten legacy raw-location deadlines before the hard privacy ceiling.

Revision ID: 0023
Revises: 0022
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Backfill legacy rows to the five-minute-early deletion deadline."""

    op.execute(
        """
        UPDATE location_samples
        SET expires_at = LEAST(
            expires_at,
            recorded_at + INTERVAL '23 hours 55 minutes'
        )
        WHERE expires_at > recorded_at + INTERVAL '23 hours 55 minutes'
        """
    )


def downgrade() -> None:
    """Keep shortened deadlines because extending privacy retention is unsafe."""
