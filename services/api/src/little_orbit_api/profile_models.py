"""Relationship-scoped avatars assigned by one partner to the other."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class RelationshipAvatar(Base):
    """One sanitized avatar chosen for a subject by their current partner."""

    __tablename__ = "relationship_avatars"
    __table_args__ = (
        UniqueConstraint("couple_id", "subject_account_id"),
        CheckConstraint("subject_account_id <> assigned_by_account_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    image_webp: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    thumbnail_webp: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    thumbnail_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
