"""Transactional APK release metadata updates shared by admin and local operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .models import ApkRelease
from .schemas import ApkReleaseInput


class PublishedReleaseImmutable(RuntimeError):
    """Raised when an operator attempts to mutate already-published release bytes."""


async def upsert_apk_release(
    session: AsyncSession,
    payload: ApkReleaseInput,
    updated_by: UUID | None,
) -> ApkRelease:
    """Create or replace one release record without committing its transaction."""

    record = await session.scalar(
        select(ApkRelease).where(ApkRelease.version == payload.version).with_for_update()
    )
    if record is not None and record.published_at is not None:
        expected = {
            "version_code": payload.version_code,
            "apk_url": str(payload.apk_url),
            "github_release_url": str(payload.github_release_url),
            "sha256": payload.sha256,
            "size_bytes": payload.size_bytes,
            "package_name": payload.package_name,
            "signer_sha256": payload.signer_sha256,
            "minimum_android": payload.minimum_android,
            "minimum_supported_version_code": payload.minimum_supported_version_code,
            "required_after": payload.required_after,
            "release_notes": payload.release_notes,
        }
        if not payload.publish or any(getattr(record, key) != value for key, value in expected.items()):
            raise PublishedReleaseImmutable("Published release metadata is immutable")
        return record
    now = SystemClock().now()
    values = {
        "version_code": payload.version_code,
        "apk_url": str(payload.apk_url),
        "github_release_url": str(payload.github_release_url),
        "sha256": payload.sha256,
        "size_bytes": payload.size_bytes,
        "package_name": payload.package_name,
        "signer_sha256": payload.signer_sha256,
        "minimum_android": payload.minimum_android,
        "minimum_supported_version_code": payload.minimum_supported_version_code,
        "required_after": payload.required_after,
        "release_notes": payload.release_notes,
        "published_at": now if payload.publish else None,
        "updated_by": updated_by,
        "updated_at": now,
    }
    if record is None:
        record = ApkRelease(version=payload.version, created_at=now, **values)
        session.add(record)
    else:
        for key, value in values.items():
            setattr(record, key, value)
    await session.flush()
    return record
