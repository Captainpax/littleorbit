"""Privacy-limited, self-hosted notification persistence."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class NotificationPreference(Base):
    """Account-wide notification choices shared by the person's Android devices."""

    __tablename__ = "notification_preferences"

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    master_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    smooches_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note_editing_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    daily_quiz_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    countdowns_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    weekly_summary_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NotificationDevice(Base):
    """One random app installation identifier scoped to an authenticated account."""

    __tablename__ = "notification_devices"
    __table_args__ = (
        UniqueConstraint("account_id", "device_id"),
        Index("ix_notification_device_active", "account_id", "last_seen_at", "disabled_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    app_version_code: Mapped[int] = mapped_column(Integer, nullable=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationEvent(Base):
    """Short-lived metadata indicating that an authorized partner alert is available."""

    __tablename__ = "notification_events"
    __table_args__ = (
        UniqueConstraint("recipient_id", "dedupe_key"),
        Index("ix_notification_event_pending", "recipient_id", "expires_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    recipient_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    legacy_consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationDelivery(Base):
    """Per-installation acknowledgement for one short-lived event."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("event_id", "device_id"),
        Index("ix_notification_delivery_pending", "device_id", "displayed_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("notification_events.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("notification_devices.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    displayed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
