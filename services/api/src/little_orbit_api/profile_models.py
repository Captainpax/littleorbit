"""Relationship-scoped avatars assigned by one partner to the other."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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


class RelationshipName(Base):
    """A relationship-scoped name assigned to one person by their partner."""

    __tablename__ = "relationship_names"
    __table_args__ = (
        UniqueConstraint("couple_id", "subject_account_id", name="uq_relationship_name_subject"),
        CheckConstraint(
            "subject_account_id <> assigned_by_account_id",
            name="ck_relationship_name_partner_only",
        ),
        CheckConstraint("revision >= 1", name="ck_relationship_name_revision"),
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
    assigned_name: Mapped[str | None] = mapped_column(String(40))
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RelationshipNameOperation(Base):
    """Thirty-day replay record for one name set or reset mutation."""

    __tablename__ = "relationship_name_operations"
    __table_args__ = (
        UniqueConstraint(
            "assigned_by_account_id",
            "operation_id",
            name="uq_relationship_name_operation_actor",
        ),
        CheckConstraint("action IN ('set', 'reset')", name="ck_relationship_name_action"),
        Index("ix_relationship_name_operations_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    assigned_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    operation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(8), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
