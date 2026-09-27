"""Add partner-assigned relationship names.

Revision ID: 0029
Revises: 0028
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create active name state and bounded idempotency records."""

    op.create_table(
        "relationship_names",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "couple_id",
            sa.Uuid(),
            sa.ForeignKey("couples.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assigned_by_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assigned_name", sa.String(length=40)),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "couple_id", "subject_account_id", name="uq_relationship_name_subject"
        ),
        sa.CheckConstraint(
            "subject_account_id <> assigned_by_account_id",
            name="ck_relationship_name_partner_only",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_relationship_name_revision"),
    )
    op.create_index("ix_relationship_names_couple_id", "relationship_names", ["couple_id"])
    op.create_index(
        "ix_relationship_names_subject_account_id",
        "relationship_names",
        ["subject_account_id"],
    )
    _create_operations()


def _create_operations() -> None:
    op.create_table(
        "relationship_name_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "couple_id",
            sa.Uuid(),
            sa.ForeignKey("couples.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assigned_by_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "assigned_by_account_id",
            "operation_id",
            name="uq_relationship_name_operation_actor",
        ),
        sa.CheckConstraint(
            "action IN ('set', 'reset')", name="ck_relationship_name_action"
        ),
    )
    op.create_index(
        "ix_relationship_name_operations_couple_id",
        "relationship_name_operations",
        ["couple_id"],
    )
    op.create_index(
        "ix_relationship_name_operations_created_at",
        "relationship_name_operations",
        ["created_at"],
    )


def downgrade() -> None:
    """Remove partner-assigned names and their retry records."""

    op.drop_table("relationship_name_operations")
    op.drop_table("relationship_names")
