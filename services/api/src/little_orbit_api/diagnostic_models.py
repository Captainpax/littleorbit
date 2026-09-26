"""Privacy-bounded opt-in Android crash diagnostics."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class CrashReport(Base):
    """Sanitized report whose raw detail expires before aggregate identity."""

    __tablename__ = "crash_reports"
    __table_args__ = (
        Index("ix_crash_reports_raw_expiry", "raw_expires_at"),
        Index("ix_crash_reports_aggregate_expiry", "aggregate_expires_at"),
        Index("ix_crash_reports_fingerprint_version", "fingerprint", "app_version_code"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    installation_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    app_version_code: Mapped[int] = mapped_column(Integer, nullable=False)
    app_version_name: Mapped[str] = mapped_column(String(40), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    exception_chain: Mapped[str | None] = mapped_column(Text)
    app_frames: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    aggregate_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
