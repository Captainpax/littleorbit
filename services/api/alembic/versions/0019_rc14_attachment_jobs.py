"""Add bounded attachment jobs and race-safe global quota accounting.

Revision ID: 0019
Revises: 0018
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create sanitizer leases and initialize the global reservation mutex."""

    op.create_table(
        "attachment_storage_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reserved_bytes", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_attachment_storage_singleton"),
        sa.CheckConstraint(
            "reserved_bytes >= 0 AND reserved_bytes <= 53687091200",
            name="ck_attachment_storage_bounds",
        ),
    )
    op.execute(
        "INSERT INTO attachment_storage_state (id, reserved_bytes, updated_at) "
        "SELECT 1, COALESCE(SUM(size_bytes), 0), now() FROM note_attachments "
        "WHERE deleted_at IS NULL "
        "AND status IN ('uploading', 'pending_scan', 'scanning', 'available')"
    )
    op.create_table(
        "attachment_jobs",
        sa.Column("attachment_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("leased_by", sa.String(length=64)),
        sa.Column("last_error", sa.String(length=40)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attachment_id"], ["note_attachments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("attachment_id"),
        sa.CheckConstraint("attempts >= 0 AND attempts <= 8", name="ck_attachment_job_attempts"),
        sa.CheckConstraint(
            "status IN ('pending', 'leased', 'completed', 'rejected')",
            name="ck_attachment_job_status",
        ),
    )
    op.create_index(
        "ix_attachment_jobs_ready", "attachment_jobs", ["status", "next_attempt_at"]
    )
    op.execute("UPDATE note_attachments SET status = 'pending_scan' WHERE status = 'scanning'")
    op.execute(
        "INSERT INTO attachment_jobs "
        "(attachment_id, status, attempts, next_attempt_at, created_at, updated_at) "
        "SELECT id, 'pending', 0, now(), now(), now() FROM note_attachments "
        "WHERE status = 'pending_scan'"
    )


def downgrade() -> None:
    """Remove RC14 job metadata and global quota accounting."""

    op.drop_index("ix_attachment_jobs_ready", table_name="attachment_jobs")
    op.drop_table("attachment_jobs")
    op.drop_table("attachment_storage_state")
