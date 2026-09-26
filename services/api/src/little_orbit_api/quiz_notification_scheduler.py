"""Scheduled creation of retry-safe daily quiz alerts."""

import logging
from datetime import date
from uuid import UUID

from sqlalchemy import select

from .clock import SystemClock
from .couple_access import lock_couple
from .database import SessionFactory
from .models import Couple, CoupleMember
from .notification_service import ensure_quiz_available_event
from .quiz_v2_service import materialize_day

LOGGER = logging.getLogger(__name__)


async def ensure_daily_quiz_notifications() -> int:
    """Materialize today's valid quiz and alert each unfinished member once."""

    today = SystemClock().now().date()
    async with SessionFactory() as session:
        couple_ids = list(
            await session.scalars(
                select(Couple.id).where(Couple.ended_at.is_(None)).order_by(Couple.id)
            )
        )
    created = 0
    for couple_id in couple_ids:
        created += await _notify_couple(couple_id, today)
    return created


async def _notify_couple(couple_id: UUID, target: date) -> int:
    """Use one transaction so a bad pairing cannot block every couple's alert."""

    async with SessionFactory() as session:
        try:
            await lock_couple(session, couple_id)
            members = list(
                await session.scalars(
                    select(CoupleMember)
                    .where(
                        CoupleMember.couple_id == couple_id,
                        CoupleMember.left_at.is_(None),
                    )
                    .order_by(CoupleMember.account_id)
                )
            )
            if len(members) != 2:
                return 0
            day = await materialize_day(session, members[0], target)
            recipients = [
                await ensure_quiz_available_event(session, day, member.account_id)
                for member in members
            ]
            await session.commit()
            return sum(recipient is not None for recipient in recipients)
        except Exception:
            await session.rollback()
            LOGGER.exception("daily quiz notification failed for couple %s", couple_id)
            return 0
