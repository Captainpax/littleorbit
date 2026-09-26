"""Calendar-aware countdown persistence kept outside the core model registry."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import Timestamped


class Countdown(Timestamped, Base):
    """Shared countdown with an optimistic revision."""

    __tablename__ = "countdowns"
    __table_args__ = (
        CheckConstraint("revision >= 0"),
        CheckConstraint("timing_kind IN ('timed', 'all_day')"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    occurs_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    timing_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="timed")
    occurs_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CountdownReminder(Base):
    """One account's private reminder choice for a shared countdown."""

    __tablename__ = "countdown_reminders"
    __table_args__ = (
        UniqueConstraint("countdown_id", "account_id", "offset_minutes"),
        CheckConstraint("offset_minutes IN (0, 60, 1440, 10080)"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    countdown_id: Mapped[UUID] = mapped_column(
        ForeignKey("countdowns.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CountdownOperation(Base):
    """Idempotency record for an offline countdown mutation."""

    __tablename__ = "countdown_operations"
    __table_args__ = (UniqueConstraint("couple_id", "operation_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(ForeignKey("couples.id", ondelete="CASCADE"))
    operation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    countdown_id: Mapped[UUID] = mapped_column(ForeignKey("countdowns.id", ondelete="CASCADE"))
    resulting_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
