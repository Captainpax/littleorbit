"""Add RC10 smooches, note lifecycle, and couple timezone.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create durable Smooch records and retry-safe note metadata state."""

    _add_couple_timezone_and_note_lifecycle()
    _create_smooches()


def _add_couple_timezone_and_note_lifecycle() -> None:
    """Add calendar-zone ownership and reversible note archiving."""

    op.add_column(
        "couples",
        sa.Column(
            "home_timezone",
            sa.String(64),
            nullable=False,
            server_default="America/Los_Angeles",
        ),
    )
    op.add_column(
        "notes", sa.Column("metadata_revision", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("notes", sa.Column("archived_at", sa.DateTime(timezone=True)))
    op.add_column("notes", sa.Column("purge_after", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_notes_metadata_revision_nonnegative", "notes", "metadata_revision >= 0"
    )
    op.create_index("ix_notes_purge_after", "notes", ["purge_after"])
    op.create_table(
        "note_metadata_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "note_id", sa.Uuid(), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "actor_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL")
        ),
        sa.Column("resulting_revision", sa.Integer(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("note_id", "operation_id"),
    )


def _create_smooches() -> None:
    """Create durable affectionate signals and delivery indexes."""

    op.create_table(
        "smooches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "couple_id", sa.Uuid(), sa.ForeignKey("couples.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "sender_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL")
        ),
        sa.Column(
            "recipient_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL")
        ),
        sa.Column("emoji", sa.String(16), nullable=False),
        sa.Column("phrase_key", sa.String(32), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("couple_id", "sender_id", "operation_id"),
    )
    op.create_index("ix_smooches_couple_id", "smooches", ["couple_id"])
    op.create_index("ix_smooches_sender_id", "smooches", ["sender_id"])
    op.create_index("ix_smooches_recipient_id", "smooches", ["recipient_id"])
    op.create_index(
        "ix_smooch_sender_sent", "smooches", ["couple_id", "sender_id", "sent_at"]
    )
    op.create_index(
        "ix_smooch_recipient_pending",
        "smooches",
        ["recipient_id", "delivered_at", "sent_at"],
    )


def downgrade() -> None:
    """Remove RC10 tables and columns."""

    op.drop_table("smooches")
    op.drop_table("note_metadata_operations")
    op.drop_index("ix_notes_purge_after", table_name="notes")
    op.drop_constraint("ck_notes_metadata_revision_nonnegative", "notes", type_="check")
    op.drop_column("notes", "purge_after")
    op.drop_column("notes", "archived_at")
    op.drop_column("notes", "metadata_revision")
    op.drop_column("couples", "home_timezone")
