"""Transactional accounting for bounded private attachment storage."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .attachment_models import AttachmentStorageState, NoteAttachment
from .attachment_storage import GLOBAL_QUOTA_BYTES, AttachmentPolicyError
from .clock import SystemClock


async def lock_storage_state(session: AsyncSession) -> AttachmentStorageState:
    """Lock the singleton storage row before any reservation changes."""

    state = await session.scalar(
        select(AttachmentStorageState)
        .where(AttachmentStorageState.id == 1)
        .with_for_update()
    )
    if state is None:
        raise RuntimeError("attachment storage state is unavailable")
    return state


async def reserve_storage(session: AsyncSession, size_bytes: int) -> None:
    """Reserve bytes atomically or fail before accepting an upload."""

    state = await lock_storage_state(session)
    if state.reserved_bytes + size_bytes > GLOBAL_QUOTA_BYTES:
        raise AttachmentPolicyError("global_quota_exceeded")
    state.reserved_bytes += size_bytes
    state.updated_at = SystemClock().now()


async def adjust_storage(session: AsyncSession, delta_bytes: int) -> None:
    """Adjust a prior reservation while refusing accounting underflow or overflow."""

    state = await lock_storage_state(session)
    next_value = state.reserved_bytes + delta_bytes
    if next_value > GLOBAL_QUOTA_BYTES:
        raise AttachmentPolicyError("global_quota_exceeded")
    if next_value < 0:
        raise RuntimeError("attachment storage accounting invariant failed")
    state.reserved_bytes = next_value
    state.updated_at = SystemClock().now()


async def reconcile_storage(session: AsyncSession) -> int:
    """Recompute accounting under the global lock after cascading maintenance."""

    state = await lock_storage_state(session)
    total = int(
        await session.scalar(
            select(func.coalesce(func.sum(NoteAttachment.size_bytes), 0)).where(
                NoteAttachment.deleted_at.is_(None),
                NoteAttachment.status.in_(
                    ("uploading", "pending_scan", "scanning", "available")
                ),
            )
        )
        or 0
    )
    if total > GLOBAL_QUOTA_BYTES:
        raise RuntimeError("attachment storage exceeds its global ceiling")
    state.reserved_bytes = total
    state.updated_at = SystemClock().now()
    return total
