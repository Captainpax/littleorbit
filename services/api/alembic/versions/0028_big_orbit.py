"""Add device-bound Big Orbit and operations state.

Revision ID: 0028
Revises: 0027
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create key-bound device, alert, job, and backup metadata tables."""

    _devices()
    _operations()


def _devices() -> None:
    op.create_table(
        "admin_devices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("public_key_spki", sa.Text(), nullable=False),
        sa.Column("key_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("credential_hash", sa.String(length=64)),
        sa.Column("credential_expires_at", sa.DateTime(timezone=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "key_fingerprint", name="uq_admin_device_key"),
    )
    op.create_index("ix_admin_devices_account_active", "admin_devices", ["account_id", "revoked_at"])
    op.create_table(
        "admin_device_challenges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("device_id", sa.Uuid(), sa.ForeignKey("admin_devices.id", ondelete="CASCADE")),
        sa.Column("challenge_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("purpose IN ('enrollment', 'session')", name="ck_admin_challenge_purpose"),
    )
    op.create_index("ix_admin_challenges_expiry", "admin_device_challenges", ["expires_at"])
    op.create_table(
        "admin_device_sessions",
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("device_id", sa.Uuid(), sa.ForeignKey("admin_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_admin_device_sessions_device_id", "admin_device_sessions", ["device_id"])


def _operations() -> None:
    op.create_table(
        "admin_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dedupe_key", sa.String(length=160), nullable=False, unique=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=300), nullable=False),
        sa.Column("action_path", sa.String(length=160)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("severity IN ('info', 'warning', 'critical')", name="ck_admin_alert_severity"),
    )
    op.create_index("ix_admin_alerts_open", "admin_alerts", ["resolved_at", "created_at"])
    op.create_table(
        "admin_alert_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("alert_id", sa.Uuid(), sa.ForeignKey("admin_alerts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.Uuid(), sa.ForeignKey("admin_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("alert_id", "device_id", name="uq_admin_alert_delivery"),
    )
    op.create_table(
        "admin_job_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_device_id", sa.Uuid(), sa.ForeignKey("admin_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_week", sa.Date()),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("requested_by", "operation_id", name="uq_admin_job_operation"),
        sa.CheckConstraint("kind IN ('learn_quizzes', 'generate_quizzes', 'backup', 'test_restore')", name="ck_admin_job_kind"),
        sa.CheckConstraint("status IN ('pending', 'running', 'passed', 'failed', 'cancelled')", name="ck_admin_job_status"),
    )
    op.create_index("ix_admin_job_pending", "admin_job_requests", ["status", "created_at"])
    op.create_table(
        "backup_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_request_id", sa.Uuid(), sa.ForeignKey("admin_job_requests.id", ondelete="SET NULL")),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("destination", sa.String(length=40), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64)),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind IN ('backup', 'test_restore')", name="ck_backup_run_kind"),
        sa.CheckConstraint("status IN ('running', 'passed', 'failed')", name="ck_backup_run_status"),
    )
    op.create_index("ix_backup_runs_created", "backup_runs", ["created_at"])


def downgrade() -> None:
    """Remove Big Orbit metadata without touching product or relationship state."""

    for table in (
        "backup_runs",
        "admin_job_requests",
        "admin_alert_deliveries",
        "admin_alerts",
        "admin_device_sessions",
        "admin_device_challenges",
        "admin_devices",
    ):
        op.drop_table(table)
