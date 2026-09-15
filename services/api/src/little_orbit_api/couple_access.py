"""Shared authorization queries for couple-scoped application services."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Couple, CoupleMember


def relationship_inactive_error() -> HTTPException:
    """Return the stable client purge signal for an inactive relationship."""

    return HTTPException(
        status.HTTP_409_CONFLICT,
        {"code": "relationship_inactive", "message": "Pair with a partner first"},
    )


async def active_member(
    session: AsyncSession, account_id: UUID
) -> CoupleMember:
    """Return active membership after authentication or fail without leaking metadata."""

    statement = select(CoupleMember).where(
        CoupleMember.account_id == account_id,
        CoupleMember.left_at.is_(None),
    )
    member = await session.scalar(statement)
    if member is None:
        raise relationship_inactive_error()
    return member


async def archived_member(
    session: AsyncSession, account_id: UUID, couple_id: UUID
) -> CoupleMember:
    """Authorize one former member without revealing another archive's existence."""

    member = await session.scalar(
        select(CoupleMember).where(
            CoupleMember.account_id == account_id,
            CoupleMember.couple_id == couple_id,
            CoupleMember.left_at.is_not(None),
        )
    )
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Archive is unavailable")
    return member


async def both_members_consent(
    session: AsyncSession, couple_id: UUID, field: str
) -> bool:
    """Check an allowlisted boolean consent field for both active members."""

    consent_fields = {
        "intimacy_enabled": CoupleMember.intimacy_enabled,
        "location_enabled": CoupleMember.location_enabled,
    }
    column = consent_fields.get(field)
    if column is None:
        raise ValueError("unknown consent field")
    count = await session.scalar(
        select(func.count())
        .select_from(CoupleMember)
        .where(
            CoupleMember.couple_id == couple_id,
            CoupleMember.left_at.is_(None),
            column.is_(True),
        )
    )
    return count == 2


async def lock_couple(session: AsyncSession, couple_id: UUID) -> Couple:
    """Serialize retry-sensitive shared mutations on one relationship row."""

    couple = await session.get(
        Couple,
        couple_id,
        with_for_update=True,
        populate_existing=True,
    )
    if couple is None or couple.ended_at is not None:
        raise relationship_inactive_error()
    return couple
