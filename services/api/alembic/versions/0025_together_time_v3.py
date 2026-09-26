"""Record durable provenance for chronological together-time estimates.

Revision ID: 0025
Revises: 0024
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Label existing durable days as legacy before algorithm v3 recomputes them."""

    op.add_column(
        "together_days",
        sa.Column(
            "estimate_method",
            sa.String(length=16),
            nullable=False,
            server_default="legacy_v2",
        ),
    )
    op.create_check_constraint(
        "ck_together_days_estimate_method",
        "together_days",
        "estimate_method IN ('legacy_v2', 'mixed', 'current_v3')",
    )
    op.alter_column("together_days", "estimate_method", server_default=None)


def downgrade() -> None:
    """Remove provenance while retaining all coordinate-free totals."""

    op.drop_constraint(
        "ck_together_days_estimate_method", "together_days", type_="check"
    )
    op.drop_column("together_days", "estimate_method")
