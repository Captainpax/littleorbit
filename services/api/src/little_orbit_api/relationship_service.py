"""Canonical account-first locking and teardown for an active relationship."""

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .activity_models import ActivityEvent, ActivitySeen
from .countdown_models import Countdown, CountdownReminder
from .models import Account, Couple, CoupleMember, LocationSample
from .notification_models import NotificationDevice, NotificationEvent
from .profile_models import RelationshipAvatar


@dataclass(frozen=True)
class LockedRelationship:
    """Relationship rows held in the global account, couple, membership lock order."""

    couple: Couple
    members: tuple[CoupleMember, CoupleMember]


async def lock_accounts(session: AsyncSession, account_ids: tuple[UUID, ...]) -> list[Account]:
    """Lock account rows in UUID order and refresh dependency-cached objects."""

    unique_ids = tuple(sorted(set(account_ids)))
    return list(
        await session.scalars(
            select(Account)
            .where(Account.id.in_(unique_ids))
            .order_by(Account.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )


async def lock_active_relationship(
    session: AsyncSession, actor_id: UUID
) -> LockedRelationship | None:
    """Lock one active relationship without member-first deadlocks."""

    couple_id = await _active_couple_id(session, actor_id)
    if couple_id is None:
        return None
    account_ids = tuple(
        await session.scalars(
            select(CoupleMember.account_id)
            .where(CoupleMember.couple_id == couple_id, CoupleMember.left_at.is_(None))
            .order_by(CoupleMember.account_id)
        )
    )
    await lock_accounts(session, account_ids)
    current_couple_id = await _active_couple_id(session, actor_id)
    if current_couple_id is None:
        return None
    if current_couple_id != couple_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pairing state changed; retry")
    couple = await session.get(
        Couple,
        couple_id,
        with_for_update=True,
        populate_existing=True,
    )
    members = tuple(
        await session.scalars(
            select(CoupleMember)
            .where(CoupleMember.couple_id == couple_id, CoupleMember.left_at.is_(None))
            .order_by(CoupleMember.account_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    valid = couple is not None and couple.ended_at is None and len(members) == 2
    valid = valid and any(member.account_id == actor_id for member in members)
    if not valid or couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pairing state changed; retry")
    return LockedRelationship(couple, (members[0], members[1]))


async def _active_couple_id(session: AsyncSession, account_id: UUID) -> UUID | None:
    """Read the active couple identifier for a locked-state recheck."""

    return cast(
        UUID | None,
        await session.scalar(
            select(CoupleMember.couple_id).where(
                CoupleMember.account_id == account_id,
                CoupleMember.left_at.is_(None),
            )
        ),
    )


async def end_active_relationship(
    session: AsyncSession, actor_id: UUID, ended_at: datetime
) -> UUID | None:
    """Stop sharing and erase ephemeral pair state under the canonical locks."""

    locked = await lock_active_relationship(session, actor_id)
    if locked is None:
        return None
    couple = locked.couple
    couple.ended_at = ended_at
    couple.updated_at = ended_at
    for member in locked.members:
        member.left_at = ended_at
        member.intimacy_enabled = False
        member.location_enabled = False
    await _delete_ephemeral_relationship_state(session, couple.id, ended_at)
    return couple.id


async def _delete_ephemeral_relationship_state(
    session: AsyncSession, couple_id: UUID, ended_at: datetime
) -> None:
    member_ids = select(CoupleMember.account_id).where(CoupleMember.couple_id == couple_id)
    await session.execute(
        delete(NotificationEvent).where(NotificationEvent.couple_id == couple_id)
    )
    await session.execute(
        update(NotificationDevice)
        .where(NotificationDevice.account_id.in_(member_ids))
        .values(
            notifications_enabled=False,
            disabled_at=ended_at,
            push_token_encrypted=None,
            push_token_hash=None,
            push_token_refreshed_at=None,
            push_token_invalidated_at=ended_at,
            push_last_attempt_at=None,
            push_last_success_at=None,
            push_failure_count=0,
        )
    )
    await session.execute(delete(LocationSample).where(LocationSample.couple_id == couple_id))
    await session.execute(
        delete(RelationshipAvatar).where(RelationshipAvatar.couple_id == couple_id)
    )
    countdown_ids = select(Countdown.id).where(Countdown.couple_id == couple_id)
    await session.execute(
        delete(CountdownReminder).where(CountdownReminder.countdown_id.in_(countdown_ids))
    )
    await session.execute(delete(ActivitySeen).where(ActivitySeen.couple_id == couple_id))
    await session.execute(delete(ActivityEvent).where(ActivityEvent.couple_id == couple_id))
