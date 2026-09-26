"""Add bounded bridge provenance and opt-in device health.

Revision ID: 0026
Revises: 0025
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Extend coordinate-free evidence without changing raw-location retention."""

    _upgrade_buckets()
    _upgrade_days()
    _create_device_health()


def _upgrade_buckets() -> None:
    op.alter_column("together_buckets", "estimated_distance_m", nullable=True)
    op.add_column(
        "together_buckets",
        sa.Column(
            "evidence_kind",
            sa.String(length=20),
            nullable=False,
            server_default="observed",
        ),
    )
    op.create_check_constraint(
        "ck_together_bucket_evidence_kind",
        "together_buckets",
        "evidence_kind IN "
        "('observed', 'bridged', 'mixed', 'apart', 'poor_accuracy', 'unverified')",
    )
    op.alter_column("together_buckets", "evidence_kind", server_default=None)
    for name in (
        "observed_seconds",
        "bridged_seconds",
        "unverified_seconds",
        "apart_seconds",
        "poor_accuracy_seconds",
    ):
        op.add_column(
            "together_buckets",
            sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
        )
    op.execute(
        "UPDATE together_buckets "
        "SET observed_seconds = duration_seconds "
        "WHERE duration_seconds > 0"
    )
    for name in (
        "observed_seconds",
        "bridged_seconds",
        "unverified_seconds",
        "apart_seconds",
        "poor_accuracy_seconds",
    ):
        op.alter_column("together_buckets", name, server_default=None)
        op.create_check_constraint(
            f"ck_together_bucket_{name}_bounds",
            "together_buckets",
            f"{name} >= 0 AND {name} <= 60",
        )
    op.create_check_constraint(
        "ck_together_bucket_counted_components",
        "together_buckets",
        "duration_seconds = observed_seconds + bridged_seconds",
    )
    op.create_check_constraint(
        "ck_together_bucket_component_total",
        "together_buckets",
        "observed_seconds + bridged_seconds + unverified_seconds + "
        "apart_seconds + poor_accuracy_seconds <= 60",
    )
def _upgrade_days() -> None:
    op.drop_constraint(
        "ck_together_day_estimated_bounds", "together_days", type_="check"
    )
    op.drop_constraint(
        "ck_together_day_corrected_bounds", "together_days", type_="check"
    )
    op.drop_constraint(
        "ck_together_days_estimate_method", "together_days", type_="check"
    )
    op.create_check_constraint(
        "ck_together_day_estimated_bounds",
        "together_days",
        "estimated_seconds >= 0 AND estimated_seconds <= 90000",
    )
    op.create_check_constraint(
        "ck_together_day_corrected_bounds",
        "together_days",
        "corrected_seconds IS NULL OR "
        "(corrected_seconds >= 0 AND corrected_seconds <= 90000)",
    )
    op.create_check_constraint(
        "ck_together_days_estimate_method",
        "together_days",
        "estimate_method IN ('legacy_v2', 'mixed', 'current_v3', 'current_v4')",
    )
    op.add_column(
        "together_days",
        sa.Column(
            "day_timezone", sa.String(length=64), nullable=False, server_default="UTC"
        ),
    )
    op.alter_column("together_days", "day_timezone", server_default=None)


def _create_device_health() -> None:
    _create_device_health_table()
    for name, columns in (
        ("ix_together_device_health_couple_id", ["couple_id"]),
        ("ix_together_device_health_account_id", ["account_id"]),
        ("ix_together_device_health_expiry", ["expires_at"]),
    ):
        op.create_index(name, "together_device_health", columns)


def _create_device_health_table() -> None:
    op.create_table(
        "together_device_health",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "couple_id",
            sa.Uuid(),
            sa.ForeignKey("couples.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("device_model", sa.String(length=80), nullable=False),
        sa.Column("battery_percent", sa.Integer(), nullable=False),
        sa.Column("charging", sa.Boolean(), nullable=False),
        sa.Column("network_transport", sa.String(length=12), nullable=False),
        sa.Column("background_location", sa.Boolean(), nullable=False),
        sa.Column("battery_unrestricted", sa.Boolean(), nullable=False),
        sa.Column("tracking_notification", sa.Boolean(), nullable=False),
        sa.Column("upload_state", sa.String(length=12), nullable=False),
        sa.Column("queue_size", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "couple_id",
            "account_id",
            "installation_id",
            name="uq_together_device_health_installation",
        ),
        sa.CheckConstraint(
            "battery_percent BETWEEN 0 AND 100",
            name="ck_together_device_health_battery",
        ),
        sa.CheckConstraint(
            "queue_size >= 0 AND queue_size <= 1000",
            name="ck_together_device_health_queue",
        ),
        sa.CheckConstraint(
            "network_transport IN "
            "('wifi', 'cellular', 'ethernet', 'other', 'offline')",
            name="ck_together_device_health_network",
        ),
        sa.CheckConstraint(
            "upload_state IN ('working', 'waiting', 'error')",
            name="ck_together_device_health_upload",
        ),
    )
def downgrade() -> None:
    """Remove reliability metadata while retaining durable totals."""

    op.drop_table("together_device_health")
    _downgrade_days()
    _downgrade_buckets()


def _downgrade_days() -> None:
    op.drop_column("together_days", "day_timezone")
    op.execute(
        "UPDATE together_days SET estimated_seconds = LEAST(estimated_seconds, 86400), "
        "corrected_seconds = CASE WHEN corrected_seconds IS NULL THEN NULL "
        "ELSE LEAST(corrected_seconds, 86400) END, "
        "estimate_method = CASE WHEN estimate_method = 'current_v4' "
        "THEN 'current_v3' ELSE estimate_method END"
    )
    op.drop_constraint(
        "ck_together_days_estimate_method", "together_days", type_="check"
    )
    op.drop_constraint(
        "ck_together_day_corrected_bounds", "together_days", type_="check"
    )
    op.drop_constraint(
        "ck_together_day_estimated_bounds", "together_days", type_="check"
    )
    op.create_check_constraint(
        "ck_together_day_estimated_bounds",
        "together_days",
        "estimated_seconds >= 0 AND estimated_seconds <= 86400",
    )
    op.create_check_constraint(
        "ck_together_day_corrected_bounds",
        "together_days",
        "corrected_seconds IS NULL OR "
        "(corrected_seconds >= 0 AND corrected_seconds <= 86400)",
    )
    op.create_check_constraint(
        "ck_together_days_estimate_method",
        "together_days",
        "estimate_method IN ('legacy_v2', 'mixed', 'current_v3')",
    )


def _downgrade_buckets() -> None:
    op.drop_constraint(
        "ck_together_bucket_evidence_kind", "together_buckets", type_="check"
    )
    op.drop_constraint(
        "ck_together_bucket_component_total", "together_buckets", type_="check"
    )
    op.drop_constraint(
        "ck_together_bucket_counted_components", "together_buckets", type_="check"
    )
    for name in (
        "poor_accuracy_seconds",
        "apart_seconds",
        "unverified_seconds",
        "bridged_seconds",
        "observed_seconds",
    ):
        op.drop_constraint(
            f"ck_together_bucket_{name}_bounds", "together_buckets", type_="check"
        )
        op.drop_column("together_buckets", name)
    op.drop_column("together_buckets", "evidence_kind")
    op.execute(
        "UPDATE together_buckets SET estimated_distance_m = 0 "
        "WHERE estimated_distance_m IS NULL"
    )
    op.alter_column("together_buckets", "estimated_distance_m", nullable=False)
