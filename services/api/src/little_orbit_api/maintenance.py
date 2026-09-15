"""Bounded privacy, deletion, and attachment maintenance jobs."""

from datetime import datetime, timedelta

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .account_deletion import complete_deletion_job
from .activity_models import ActivityEvent
from .attachment_maintenance import (
    delete_attachment_files,
    delete_orphan_files,
    prepare_attachment_cleanup,
)
from .attachment_models import NoteAttachment
from .attachment_quota import reconcile_storage
from .clock import SystemClock
from .config import get_settings
from .database import SessionFactory
from .diagnostics import purge_diagnostics
from .models import (
    DeletionJob,
    LocationSample,
    Note,
    OneUseToken,
    Session,
    TogetherBucket,
)
from .notification_service import purge_notification_state
from .rate_limit import purge_rate_limit_state
from .together_models import RelationshipStartProposal, TogetherOperation


async def run_maintenance_once() -> None:
    """Apply one transaction of privacy expiry and scheduled deletion work."""

    now = SystemClock().now()
    async with SessionFactory() as session:
        attachment_keys = await prepare_attachment_cleanup(session, now)
        await purge_expired_records(session, now)
        jobs = list(
            await session.scalars(
                select(DeletionJob)
                .where(
                    DeletionJob.status == "scheduled",
                    DeletionJob.execute_after <= now,
                    DeletionJob.account_id.is_not(None),
                )
                .with_for_update(skip_locked=True)
            )
        )
        for job in jobs:
            attachment_keys.extend(await complete_deletion_job(session, job, now))
        await reconcile_storage(session)
        known_keys = set(
            await session.scalars(
                select(NoteAttachment.storage_key).where(
                    NoteAttachment.deleted_at.is_(None),
                    NoteAttachment.status.in_(
                        ("uploading", "pending_scan", "scanning", "available")
                    ),
                )
            )
        )
        await session.commit()
    storage_root = get_settings().attachment_storage_dir
    await delete_attachment_files(storage_root, attachment_keys)
    await delete_orphan_files(storage_root, known_keys, now)


async def purge_expired_records(session: AsyncSession, now: datetime) -> None:
    """Apply bounded privacy retention and proposal expiration policies."""

    await purge_expired_location_samples(session, now)
    await session.execute(
        delete(TogetherBucket).where(TogetherBucket.bucket_start < now - timedelta(days=30))
    )


async def purge_expired_location_samples(session: AsyncSession, now: datetime) -> None:
    """Delete raw locations and the remaining bounded maintenance records."""

    await session.execute(
        delete(LocationSample).where(
            or_(
                LocationSample.expires_at <= now,
                LocationSample.recorded_at <= now - timedelta(hours=24),
            )
        )
    )
    await session.execute(
        delete(OneUseToken).where(OneUseToken.expires_at <= now - timedelta(days=7))
    )
    await session.execute(delete(Session).where(Session.expires_at <= now - timedelta(days=7)))
    await purge_rate_limit_state(session, now)
    await purge_diagnostics(session, now)
    await session.execute(
        delete(Note).where(Note.purge_after.is_not(None), Note.purge_after <= now)
    )
    await session.execute(
        delete(ActivityEvent).where(ActivityEvent.created_at <= now - timedelta(days=30))
    )
    await purge_notification_state(session, now)
    await session.execute(
        update(RelationshipStartProposal)
        .where(
            RelationshipStartProposal.status == "pending",
            RelationshipStartProposal.expires_at <= now,
        )
        .values(status="expired", decided_at=now)
    )
    await session.execute(
        delete(TogetherOperation).where(TogetherOperation.created_at <= now - timedelta(days=30))
    )
    await session.execute(
        delete(RelationshipStartProposal).where(
            RelationshipStartProposal.status != "pending",
            RelationshipStartProposal.created_at <= now - timedelta(days=90),
        )
    )
