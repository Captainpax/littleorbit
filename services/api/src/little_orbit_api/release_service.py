"""Transactional APK release metadata updates shared by admin and local operations."""

from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .config import get_settings
from .models import ApkRelease
from .release_artifacts import (
    is_hosted_apk_url,
    is_hosted_wear_apk_url,
    verify_release_artifact,
    verify_wear_release_artifact,
)
from .schemas import ApkReleaseInput


class PublishedReleaseImmutable(RuntimeError):
    """Raised when an operator attempts to mutate already-published release bytes."""


async def upsert_apk_release(
    session: AsyncSession,
    payload: ApkReleaseInput,
    updated_by: UUID | None,
) -> ApkRelease:
    """Create or replace one release record without committing its transaction."""

    await _verify_hosted_artifacts(payload)
    record = await session.scalar(
        select(ApkRelease).where(ApkRelease.version == payload.version).with_for_update()
    )
    values = _metadata_values(payload)
    if record is not None and record.published_at is not None:
        _require_immutable_retry(record, payload, values)
        return record
    now = SystemClock().now()
    persisted = {
        **values,
        "published_at": now if payload.publish else None,
        "updated_by": updated_by,
        "updated_at": now,
    }
    if record is None:
        record = ApkRelease(version=payload.version, created_at=now, **persisted)
        session.add(record)
    else:
        for key, value in persisted.items():
            setattr(record, key, value)
    await session.flush()
    return record


async def _verify_hosted_artifacts(payload: ApkReleaseInput) -> None:
    """Fail publication before its transaction if local immutable bytes differ."""

    if payload.publish and is_hosted_apk_url(str(payload.apk_url), payload.version):
        await run_in_threadpool(
            verify_release_artifact,
            get_settings().release_storage_dir,
            payload.version,
            payload.size_bytes,
            payload.sha256,
        )
    if (
        payload.publish
        and payload.wear_apk_url is not None
        and payload.wear_size_bytes is not None
        and payload.wear_sha256 is not None
        and is_hosted_wear_apk_url(str(payload.wear_apk_url), payload.version)
    ):
        await run_in_threadpool(
            verify_wear_release_artifact,
            get_settings().release_storage_dir,
            payload.version,
            payload.wear_size_bytes,
            payload.wear_sha256,
        )


def _metadata_values(payload: ApkReleaseInput) -> dict[str, object]:
    """Map validated request data to immutable persistence fields."""

    return {
        "version_code": payload.version_code,
        "apk_url": str(payload.apk_url),
        "github_release_url": str(payload.github_release_url),
        "sha256": payload.sha256,
        "size_bytes": payload.size_bytes,
        "package_name": payload.package_name,
        "signer_sha256": payload.signer_sha256,
        "wear_apk_url": str(payload.wear_apk_url) if payload.wear_apk_url else None,
        "wear_sha256": payload.wear_sha256,
        "wear_size_bytes": payload.wear_size_bytes,
        "wear_package_name": payload.wear_package_name,
        "wear_version_code": payload.wear_version_code,
        "wear_minimum_android": payload.wear_minimum_android,
        "minimum_android": payload.minimum_android,
        "minimum_supported_version_code": payload.minimum_supported_version_code,
        "required_after": payload.required_after,
        "release_notes": payload.release_notes,
    }


def _require_immutable_retry(
    record: ApkRelease, payload: ApkReleaseInput, expected: dict[str, object]
) -> None:
    """Permit an exact published retry and reject every metadata mutation."""

    changed = any(getattr(record, key) != value for key, value in expected.items())
    if not payload.publish or changed:
        raise PublishedReleaseImmutable("Published release metadata is immutable")
