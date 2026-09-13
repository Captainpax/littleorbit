"""Persistence models for note metadata operations and Smooches."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class NoteMetadataOperation(Base):
    """Retry-safe title or archive mutation, separate from body OT revisions."""

    __tablename__ = "note_metadata_operations"
    __table_args__ = (UniqueConstraint("note_id", "operation_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    note_id: Mapped[UUID] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"))
    operation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    resulting_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    result: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Smooch(Base):
    """One durable, rate-limited affectionate signal between active partners."""

    __tablename__ = "smooches"
    __table_args__ = (
        UniqueConstraint("couple_id", "sender_id", "operation_id"),
        Index("ix_smooch_sender_sent", "couple_id", "sender_id", "sent_at"),
        Index("ix_smooch_recipient_pending", "recipient_id", "delivered_at", "sent_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    operation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), index=True
    )
    sender_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), index=True
    )
    recipient_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), index=True
    )
    emoji: Mapped[str] = mapped_column(String(16), nullable=False)
    phrase_key: Mapped[str] = mapped_column(String(32), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
