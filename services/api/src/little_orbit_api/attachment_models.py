"""Private persistence models for resumable note attachments."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class NoteAttachment(Base):
    """One couple-scoped file that remains private until scanning succeeds."""

    __tablename__ = "note_attachments"
    __table_args__ = (
        UniqueConstraint("note_id", "operation_id"),
        UniqueConstraint("storage_key"),
        CheckConstraint("size_bytes > 0 AND size_bytes <= 104857600"),
        CheckConstraint("uploaded_bytes >= 0 AND uploaded_bytes <= size_bytes"),
        Index("ix_note_attachments_couple_status", "couple_id", "status"),
        Index("ix_note_attachments_note_created", "note_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    note_id: Mapped[UUID] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), nullable=False
    )
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    operation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="uploading")
    rejection_reason: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AttachmentJob(Base):
    """Bounded sanitizer job with an expiring lease and explicit retry state."""

    __tablename__ = "attachment_jobs"
    __table_args__ = (
        CheckConstraint("attempts >= 0 AND attempts <= 8"),
        CheckConstraint("status IN ('pending', 'leased', 'completed', 'rejected')"),
        Index("ix_attachment_jobs_ready", "status", "next_attempt_at"),
    )

    attachment_id: Mapped[UUID] = mapped_column(
        ForeignKey("note_attachments.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    leased_by: Mapped[str | None] = mapped_column(String(64))
    last_error: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AttachmentStorageState(Base):
    """Singleton mutex and accounting row for the global private-media ceiling."""

    __tablename__ = "attachment_storage_state"
    __table_args__ = (CheckConstraint("reserved_bytes >= 0"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
