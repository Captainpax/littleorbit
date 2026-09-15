"""Persistence records owned by the RC6 together-time subsystem."""

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
        CheckConstraint("estimated_seconds >= 0 AND estimated_seconds <= 86400"),
        CheckConstraint(
            "corrected_seconds IS NULL OR "
            "(corrected_seconds >= 0 AND corrected_seconds <= 86400)"
        ),
        CheckConstraint("revision >= 0"),
        Index("ix_together_days_couple_day", "couple_id", "day"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE")
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    estimated_seconds: Mapped[int] = mapped_column(nullable=False, default=0)
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
