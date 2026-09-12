"""Public signed APK release metadata and resumable first-party downloads."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings, get_settings
from ..database import session_scope
from ..models import ApkRelease
from ..release_artifacts import (
    APK_MEDIA_TYPE,
    ReleaseArtifactUnavailable,
    verify_release_artifact,
)
from ..schemas import ApkReleaseResponse

router = APIRouter(prefix="/v1/releases", tags=["releases"])


@router.get("/current", response_model=ApkReleaseResponse)
async def current_release(
    session: AsyncSession = Depends(session_scope),
) -> ApkReleaseResponse:
    """Return the most recently published signed release."""

    release = await session.scalar(
        select(ApkRelease)
        .where(
            ApkRelease.published_at.is_not(None),
            ApkRelease.version_code.is_not(None),
            ApkRelease.size_bytes.is_not(None),
            ApkRelease.package_name.is_not(None),
            ApkRelease.signer_sha256.is_not(None),
            ApkRelease.minimum_supported_version_code.is_not(None),
        )
        .order_by(ApkRelease.version_code.desc())
        .limit(1)
    )
    if release is None or release.published_at is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No signed release is published")
    version_code = release.version_code
    size_bytes = release.size_bytes
    package_name = release.package_name
    signer_sha256 = release.signer_sha256
    minimum_supported_version_code = release.minimum_supported_version_code
    if (
        version_code is None
        or size_bytes is None
        or package_name is None
        or signer_sha256 is None
        or minimum_supported_version_code is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No signed release is published")
    return ApkReleaseResponse(
        version=release.version,
        version_code=version_code,
        apk_url=release.apk_url,
        github_release_url=release.github_release_url,
        sha256=release.sha256,
        size_bytes=size_bytes,
        package_name=package_name,
        signer_sha256=signer_sha256,
        minimum_android=release.minimum_android,
        minimum_supported_version_code=minimum_supported_version_code,
        required_after=release.required_after,
        release_notes=release.release_notes,
        published_at=release.published_at,
    )


@router.api_route("/{version}/apk", methods=["GET", "HEAD"], response_class=FileResponse)
async def download_release(
    version: Annotated[
        str,
        Path(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$", max_length=40),
    ],
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """Serve verified immutable APK bytes with standard HTTP range support."""

    release = await session.scalar(
        select(ApkRelease).where(
            ApkRelease.version == version,
            ApkRelease.published_at.is_not(None),
            ApkRelease.size_bytes.is_not(None),
        )
    )
    if release is None or release.size_bytes is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Signed release not found")
    try:
        artifact = await run_in_threadpool(
            verify_release_artifact,
            settings.release_storage_dir,
            version,
            release.size_bytes,
            release.sha256,
        )
    except ReleaseArtifactUnavailable as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Signed release temporarily unavailable",
        ) from error
    return FileResponse(
        artifact.path,
        media_type=APK_MEDIA_TYPE,
        filename=artifact.filename,
        stat_result=artifact.stat,
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{release.sha256}"',
            "X-Checksum-SHA256": release.sha256,
        },
    )
