"""Content-free scheduling and lease fencing for shared-GPU work."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .admin_device_models import AdminJobRequest
from .config import Settings
from .database import SessionFactory
from .quiz_intelligence_models import AiRun, AiWorkItem

WEEKLY_LEARNING = "weekly_learning"
WEEKLY_GENERATION = "weekly_generation"
ADMIN_LEARNING = "admin_learning"
ADMIN_GENERATION = "admin_generation"
ADMIN_REGENERATION = "admin_regeneration"

ADMIN_WORK_KINDS = {
    "learn_quizzes": ADMIN_LEARNING,
    "generate_quizzes": ADMIN_GENERATION,
    "regenerate_quizzes": ADMIN_REGENERATION,
}


@dataclass(frozen=True)
class AiWorkLease:
    """Opaque authority to heartbeat or finish one exact queue claim."""

    id: UUID
    kind: str
    scheduled_at: datetime
    token: UUID


class AiWorkLeaseExpired(RuntimeError):
    """Raised before a transaction can commit under a replaced queue token."""


def latest_due_date(
    current: datetime, weekday: int, hour: int, timezone: str = "UTC"
) -> date:
    """Return the latest local schedule date, including across DST transitions."""

    zone = _zone(timezone)
    aware = current.astimezone(zone)
    candidate = aware.date() - timedelta(days=(aware.weekday() - weekday) % 7)
    scheduled = datetime.combine(candidate, time(hour=hour), tzinfo=zone)
    if scheduled > aware:
        candidate -= timedelta(days=7)
    return candidate


async def enqueue_due_weekly_work(now: datetime, settings: Settings) -> None:
    """Persist the latest due Saturday and Sunday jobs without duplicating them."""

    jobs = (
        (WEEKLY_LEARNING, 5, settings.ai_learning_local_hour),
        (WEEKLY_GENERATION, 6, settings.ai_generation_local_hour),
    )
    async with SessionFactory() as session:
        for kind, weekday, hour in jobs:
            due = latest_due_date(now, weekday, hour, settings.ai_schedule_timezone)
            scheduled = _scheduled_instant(due, hour, settings.ai_schedule_timezone)
            next_attempt: datetime | None = scheduled
            if kind == WEEKLY_GENERATION:
                status = await session.scalar(
                    select(AiRun.status).where(
                        AiRun.run_key == f"generate:{(due + timedelta(days=1)).isoformat()}"
                    )
                )
                if status in {"passed", "fallback"}:
                    next_attempt = None
            await session.execute(
                insert(AiWorkItem)
                .values(
                    id=uuid4(),
                    kind=kind,
                    scheduled_at=scheduled,
                    next_attempt_at=next_attempt,
                    attempt_count=0,
                )
                .on_conflict_do_nothing()
            )
        await session.commit()


async def enqueue_pending_admin_work(now: datetime, stale_after: timedelta) -> None:
    """Mirror allowlisted AI admin jobs into the same ordered GPU queue."""

    stale = now - stale_after
    async with SessionFactory() as session:
        records = list(
            await session.scalars(
                select(AdminJobRequest).where(
                    AdminJobRequest.kind.in_(tuple(ADMIN_WORK_KINDS)),
                    or_(
                        AdminJobRequest.status == "pending",
                        and_(
                            AdminJobRequest.status == "running",
                            or_(
                                AdminJobRequest.started_at.is_(None),
                                AdminJobRequest.started_at <= stale,
                            ),
                        ),
                    ),
                )
            )
        )
        for record in records:
            await session.execute(
                insert(AiWorkItem)
                .values(
                    id=record.id,
                    kind=ADMIN_WORK_KINDS[record.kind],
                    scheduled_at=record.created_at,
                    next_attempt_at=record.created_at,
                    attempt_count=0,
                )
                .on_conflict_do_nothing(index_elements=[AiWorkItem.id])
            )
        await session.commit()


async def claim_due_work(
    now: datetime, *, stale_after: timedelta, minimum_gap: timedelta
) -> AiWorkLease | None:
    """Claim the oldest due item after the caller has acquired the host file lock."""

    async with SessionFactory() as session:
        latest_activity = await session.scalar(select(func.max(AiWorkItem.heartbeat_at)))
        if latest_activity is not None and latest_activity > now - minimum_gap:
            return None
        record = await session.scalar(
            select(AiWorkItem)
            .where(
                AiWorkItem.next_attempt_at.is_not(None),
            )
            .order_by(AiWorkItem.scheduled_at, AiWorkItem.kind, AiWorkItem.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if (
            record is None
            or record.next_attempt_at is None
            or record.next_attempt_at > now
            or (
                record.lease_token is not None
                and record.heartbeat_at is not None
                and record.heartbeat_at > now - stale_after
            )
        ):
            return None
        token = uuid4()
        record.lease_token = token
        record.heartbeat_at = now
        record.attempt_count += 1
        await session.commit()
        return AiWorkLease(record.id, record.kind, record.scheduled_at, token)


async def defer_due_work(now: datetime, retry_after: timedelta) -> bool:
    """Move only the oldest unleased item when another stack currently owns the GPU."""

    async with SessionFactory() as session:
        record = await session.scalar(
            select(AiWorkItem)
            .where(
                AiWorkItem.next_attempt_at.is_not(None),
            )
            .order_by(AiWorkItem.scheduled_at, AiWorkItem.kind, AiWorkItem.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if (
            record is None
            or record.next_attempt_at is None
            or record.next_attempt_at > now
            or record.lease_token is not None
        ):
            return False
        record.next_attempt_at = now + retry_after
        await session.commit()
        return True


async def heartbeat_work(lease: AiWorkLease, now: datetime) -> bool:
    """Refresh one lease only when its opaque token still matches."""

    return await _fenced_update(
        lease,
        {AiWorkItem.heartbeat_at: now},
    )


async def complete_work(lease: AiWorkLease, now: datetime) -> bool:
    """Mark one item complete while retaining its deduplication tombstone."""

    return await _fenced_update(
        lease,
        {
            AiWorkItem.next_attempt_at: None,
            AiWorkItem.lease_token: None,
            AiWorkItem.heartbeat_at: now,
        },
    )


async def retry_work(lease: AiWorkLease, now: datetime, retry_after: timedelta) -> bool:
    """Release a failed claim into its next bounded six-hour slot."""

    return await _fenced_update(
        lease,
        {
            AiWorkItem.next_attempt_at: now + retry_after,
            AiWorkItem.lease_token: None,
            AiWorkItem.heartbeat_at: now,
        },
    )


async def lease_is_current(lease: AiWorkLease) -> bool:
    """Fence side-effectful work immediately before its application claim."""

    async with SessionFactory() as session:
        token = await session.scalar(
            select(AiWorkItem.lease_token).where(AiWorkItem.id == lease.id)
        )
    return token == lease.token


async def require_current_lease(
    session: AsyncSession, lease: AiWorkLease | None
) -> None:
    """Lock and fence the queue row inside the transaction applying a result."""

    if lease is None:
        return
    record = await session.get(AiWorkItem, lease.id, with_for_update=True)
    if record is None or record.lease_token != lease.token:
        raise AiWorkLeaseExpired("AI work lease expired before result commit")


async def _fenced_update(
    lease: AiWorkLease, values: dict[object, object]
) -> bool:
    async with SessionFactory() as session:
        result = await session.execute(
            update(AiWorkItem)
            .where(
                AiWorkItem.id == lease.id,
                AiWorkItem.lease_token == lease.token,
            )
            .values(values)
        )
        await session.commit()
    return result.rowcount == 1


def _scheduled_instant(target: date, hour: int, timezone: str) -> datetime:
    return datetime.combine(target, time(hour=hour), tzinfo=_zone(timezone)).astimezone(UTC)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("AI schedule timezone is not installed") from exc
