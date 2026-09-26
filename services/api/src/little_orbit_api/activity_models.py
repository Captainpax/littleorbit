"""Privacy-minimized in-app activity persistence."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ActivityEvent(Base):
    """One content-free event in an active couple's 30-day timeline."""

    __tablename__ = "activity_events"
    __table_args__ = (
        UniqueConstraint("couple_id", "dedupe_key"),
        UniqueConstraint("couple_id", "sequence"),
        Index("ix_activity_couple_created", "couple_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[UUID | None] = mapped_column(Uuid)
    target_title: Mapped[str | None] = mapped_column(String(120))
    emoji: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ActivitySeen(Base):
    """Highest event sequence visibly viewed by one active member."""

    __tablename__ = "activity_seen"
    __table_args__ = (UniqueConstraint("couple_id", "account_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    through_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
