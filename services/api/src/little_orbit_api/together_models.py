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
        ForeignKey("couples.id", ondelete="CASCADE"), index=True
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
