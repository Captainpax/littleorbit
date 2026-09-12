"""Private processed-image persistence kept outside the core model registry."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class AccountProfilePhoto(Base):
    """Private normalized profile image owned by exactly one account."""

    __tablename__ = "account_profile_photos"

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    image_webp: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    thumbnail_webp: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    thumbnail_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
