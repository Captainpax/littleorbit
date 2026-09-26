"""Add RC6 relationship-date consensus, proximity state, and Wear metadata.

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create RC6 state without changing existing dates or together-time history."""

    op.add_column("couples", sa.Column("proximity_processed_through", sa.DateTime(timezone=True)))
    op.add_column(
        "couples",
        sa.Column(
            "proximity_algorithm_version", sa.Integer(), nullable=False, server_default="2"
        ),
    )
    op.add_column(
        "together_buckets",
        sa.Column("algorithm_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_location_samples_couple_account_recorded",
        "location_samples",
        ["couple_id", "account_id", "recorded_at"],
    )
    op.create_index(
        "ix_together_buckets_couple_start",
        "together_buckets",
        ["couple_id", "bucket_start"],
    )
    _create_relationship_start_proposals()
    _create_together_operations()
    _add_wear_release_columns()


def _create_relationship_start_proposals() -> None:
    op.create_table(
        "relationship_start_proposals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "couple_id", sa.Uuid(), sa.ForeignKey("couples.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "proposed_by", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL")
        ),
        sa.Column("proposed_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "decided_by", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL")
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'cancelled', 'expired')"
        ),
    )
    op.create_index(
        "ix_relationship_start_proposals_couple_id",
        "relationship_start_proposals",
        ["couple_id"],
    )
    op.create_index(
        "ix_relationship_start_proposals_proposed_by",
        "relationship_start_proposals",
        ["proposed_by"],
    )
    op.create_index(
        "uq_pending_relationship_start_proposal",
        "relationship_start_proposals",
        ["couple_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def _create_together_operations() -> None:
    op.create_table(
        "together_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "couple_id", sa.Uuid(), sa.ForeignKey("couples.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "account_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="SET NULL")
        ),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("couple_id", "account_id", "operation_id"),
    )
    op.create_index("ix_together_operations_couple_id", "together_operations", ["couple_id"])
    op.create_index("ix_together_operations_account_id", "together_operations", ["account_id"])


def _add_wear_release_columns() -> None:
    for name, type_ in (
        ("wear_apk_url", sa.Text()),
        ("wear_sha256", sa.String(64)),
        ("wear_size_bytes", sa.BigInteger()),
        ("wear_package_name", sa.String(160)),
        ("wear_version_code", sa.Integer()),
        ("wear_minimum_android", sa.Integer()),
    ):
        op.add_column("apk_releases", sa.Column(name, type_))


def downgrade() -> None:
    """Remove RC6 state while retaining all original columns and records."""

    for name in (
        "wear_minimum_android",
        "wear_version_code",
        "wear_package_name",
        "wear_size_bytes",
        "wear_sha256",
        "wear_apk_url",
    ):
        op.drop_column("apk_releases", name)
    op.drop_table("together_operations")
    op.drop_table("relationship_start_proposals")
    op.drop_index("ix_together_buckets_couple_start", table_name="together_buckets")
    op.drop_index(
        "ix_location_samples_couple_account_recorded", table_name="location_samples"
    )
    op.drop_column("together_buckets", "algorithm_version")
    op.drop_column("couples", "proximity_algorithm_version")
    op.drop_column("couples", "proximity_processed_through")
