"""Add private resumable note attachments.

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create couple-scoped attachment upload and scan state."""

    op.create_table(
        "note_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("note_id", sa.Uuid(), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("couple_id", sa.Uuid(), sa.ForeignKey("couples.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(80), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="uploading"),
        sa.Column("rejection_reason", sa.String(40)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("note_id", "operation_id"),
        sa.UniqueConstraint("storage_key"),
        sa.CheckConstraint("size_bytes > 0 AND size_bytes <= 104857600"),
        sa.CheckConstraint("uploaded_bytes >= 0 AND uploaded_bytes <= size_bytes"),
    )
    op.create_index(
        "ix_note_attachments_couple_status", "note_attachments", ["couple_id", "status"]
    )
    op.create_index(
        "ix_note_attachments_note_created", "note_attachments", ["note_id", "created_at"]
    )


def downgrade() -> None:
    """Remove private note attachment state."""

    op.drop_table("note_attachments")
