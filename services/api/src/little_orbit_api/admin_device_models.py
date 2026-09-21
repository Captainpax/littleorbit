"""Device-bound Big Orbit administration and content-free operations state."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class AdminDevice(Base):
    """One explicitly enrolled Android Keystore public key."""

    __tablename__ = "admin_devices"
    __table_args__ = (
        UniqueConstraint("account_id", "key_fingerprint", name="uq_admin_device_key"),
        Index("ix_admin_devices_account_active", "account_id", "revoked_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    public_key_spki: Mapped[str] = mapped_column(Text, nullable=False)
    key_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_hash: Mapped[str | None] = mapped_column(String(64))
    credential_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AdminDeviceChallenge(Base):
    """Short-lived challenge that proves possession without storing a signature."""

    __tablename__ = "admin_device_challenges"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('enrollment', 'session')", name="ck_admin_challenge_purpose"
        ),
        Index("ix_admin_challenges_expiry", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("admin_devices.id", ondelete="CASCADE")
    )
    challenge_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AdminDeviceSession(Base):
    """Binds one ordinary short session to one approved Big Orbit device."""

    __tablename__ = "admin_device_sessions"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("admin_devices.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AdminAlert(Base):
    """Content-free operational item surfaced in the Big Orbit action inbox."""

    __tablename__ = "admin_alerts"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')", name="ck_admin_alert_severity"
        ),
        UniqueConstraint("dedupe_key", name="uq_admin_alert_dedupe"),
        Index("ix_admin_alerts_open", "resolved_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    action_path: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminAlertDelivery(Base):
    """Per-device acknowledgement so one phone never consumes another's alert."""

    __tablename__ = "admin_alert_deliveries"
    __table_args__ = (
        UniqueConstraint("alert_id", "device_id", name="uq_admin_alert_delivery"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    alert_id: Mapped[UUID] = mapped_column(
        ForeignKey("admin_alerts.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("admin_devices.id", ondelete="CASCADE"), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AdminJobRequest(Base):
    """Typed, idempotent request consumed by a dedicated worker or host runner."""

    __tablename__ = "admin_job_requests"
    __table_args__ = (
        UniqueConstraint("requested_by", "operation_id", name="uq_admin_job_operation"),
        CheckConstraint(
            "kind IN ('learn_quizzes', 'generate_quizzes', 'backup', 'test_restore')",
            name="ck_admin_job_kind",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'passed', 'failed', 'cancelled')",
            name="ck_admin_job_status",
        ),
        Index("ix_admin_job_pending", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    operation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    requested_by: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    requested_device_id: Mapped[UUID] = mapped_column(
        ForeignKey("admin_devices.id", ondelete="CASCADE"), nullable=False
    )
    target_week: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    result_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BackupRun(Base):
    """Content-free evidence for encrypted backup and restore verification."""

    __tablename__ = "backup_runs"
    __table_args__ = (
        CheckConstraint("kind IN ('backup', 'test_restore')", name="ck_backup_run_kind"),
        CheckConstraint(
            "status IN ('running', 'passed', 'failed')", name="ck_backup_run_status"
        ),
        Index("ix_backup_runs_created", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("admin_job_requests.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    destination: Mapped[str] = mapped_column(String(40), nullable=False)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    details_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
