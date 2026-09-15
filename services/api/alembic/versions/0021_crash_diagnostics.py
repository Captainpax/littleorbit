"""Add privacy-bounded opt-in crash diagnostics.

Revision ID: 0021
Revises: 0020
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the raw-30-day and aggregate-90-day diagnostic store."""

    op.create_table(
        "crash_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("installation_hash", sa.String(length=64), nullable=False),
        sa.Column("app_version_code", sa.Integer(), nullable=False),
        sa.Column("app_version_name", sa.String(length=40), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("exception_chain", sa.Text()),
        sa.Column("app_frames", sa.Text()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("aggregate_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crash_reports_raw_expiry", "crash_reports", ["raw_expires_at"])
    op.create_index(
        "ix_crash_reports_aggregate_expiry", "crash_reports", ["aggregate_expires_at"]
    )
    op.create_index(
        "ix_crash_reports_fingerprint_version",
        "crash_reports",
        ["fingerprint", "app_version_code"],
    )


def downgrade() -> None:
    """Remove all opt-in diagnostic data."""

    op.drop_index("ix_crash_reports_fingerprint_version", table_name="crash_reports")
    op.drop_index("ix_crash_reports_aggregate_expiry", table_name="crash_reports")
    op.drop_index("ix_crash_reports_raw_expiry", table_name="crash_reports")
    op.drop_table("crash_reports")
