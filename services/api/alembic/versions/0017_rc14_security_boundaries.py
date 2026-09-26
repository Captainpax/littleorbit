"""Add bounded throttle counters and staged administrator MFA replacement.

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create privacy-minimized counters and pending MFA enrollment storage."""

    op.create_table(
        "rate_limit_buckets",
        sa.Column("scope", sa.String(length=48), nullable=False),
        sa.Column("subject_hash", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("scope", "subject_hash"),
        sa.CheckConstraint("count >= 1", name="ck_rate_limit_bucket_positive"),
    )
    op.create_index(
        "ix_rate_limit_buckets_expiry",
        "rate_limit_buckets",
        ["scope", "window_started_at"],
    )
    op.add_column("admin_mfa", sa.Column("pending_encrypted_secret", sa.Text()))
    op.add_column(
        "admin_mfa", sa.Column("pending_created_at", sa.DateTime(timezone=True))
    )


def downgrade() -> None:
    """Remove RC14 security state without changing an enrolled MFA factor."""

    op.drop_column("admin_mfa", "pending_created_at")
    op.drop_column("admin_mfa", "pending_encrypted_secret")
    op.drop_index("ix_rate_limit_buckets_expiry", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
