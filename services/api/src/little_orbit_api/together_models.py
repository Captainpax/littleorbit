"""Persistence records owned by the RC6 together-time subsystem."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class RelationshipStartProposal(Base):
    """Seven-day, mutually decided relationship-start-date proposal."""

    __tablename__ = "relationship_start_proposals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'cancelled', 'expired')"
        ),
        Index(
            "uq_pending_relationship_start_proposal",
            "couple_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE")
    )
    proposed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), index=True
    )
    proposed_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TogetherOperation(Base):
    """Retry-safe relationship-date operation scoped to one member."""

    __tablename__ = "together_operations"
    __table_args__ = (UniqueConstraint("couple_id", "account_id", "operation_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), index=True
    )
    operation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    result: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TogetherDay(Base):
    """Durable coordinate-free daily estimate with an optional audited correction."""

    __tablename__ = "together_days"
    __table_args__ = (
        UniqueConstraint("couple_id", "day"),
        CheckConstraint("estimated_seconds >= 0 AND estimated_seconds <= 90000"),
        CheckConstraint(
            "corrected_seconds IS NULL OR "
            "(corrected_seconds >= 0 AND corrected_seconds <= 90000)"
        ),
        CheckConstraint("revision >= 0"),
        CheckConstraint(
            "estimate_method IN ('legacy_v2', 'mixed', 'current_v3', 'current_v4')"
        ),
        Index("ix_together_days_couple_day", "couple_id", "day"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE")
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    day_timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="UTC"
    )
    estimated_seconds: Mapped[int] = mapped_column(nullable=False, default=0)
    estimate_method: Mapped[str] = mapped_column(
        String(16), nullable=False, default="current_v3"
    )
    corrected_seconds: Mapped[int | None] = mapped_column()
    revision: Mapped[int] = mapped_column(nullable=False, default=0)
    corrected_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    correction_reason: Mapped[str | None] = mapped_column(String(240))
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @property
    def effective_seconds(self) -> int:
        """Return the explicit correction when present, otherwise the estimate."""

        return self.corrected_seconds if self.corrected_seconds is not None else self.estimated_seconds


class TogetherDeviceHealth(Base):
    """Latest opt-in content-free collection health for one installation."""

    __tablename__ = "together_device_health"
    __table_args__ = (
        UniqueConstraint("couple_id", "account_id", "installation_id"),
        CheckConstraint("battery_percent BETWEEN 0 AND 100"),
        CheckConstraint("queue_size >= 0 AND queue_size <= 1000"),
        CheckConstraint(
            "network_transport IN ('wifi', 'cellular', 'ethernet', 'other', 'offline')"
        ),
        CheckConstraint("upload_state IN ('working', 'waiting', 'error')"),
        Index("ix_together_device_health_expiry", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    installation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    device_model: Mapped[str] = mapped_column(String(80), nullable=False)
    battery_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    charging: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_transport: Mapped[str] = mapped_column(String(12), nullable=False)
    background_location: Mapped[bool] = mapped_column(Boolean, nullable=False)
    battery_unrestricted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tracking_notification: Mapped[bool] = mapped_column(Boolean, nullable=False)
    upload_state: Mapped[str] = mapped_column(String(12), nullable=False)
    queue_size: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
