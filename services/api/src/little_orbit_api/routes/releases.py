"""Public signed APK release metadata."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import session_scope
from ..models import ApkRelease
from ..schemas import ApkReleaseResponse

router = APIRouter(prefix="/v1/releases", tags=["releases"])


@router.get("/current", response_model=ApkReleaseResponse)
async def current_release(
    session: AsyncSession = Depends(session_scope),
) -> ApkReleaseResponse:
    """Return the most recently published release without proxying its APK."""

    release = await session.scalar(
        select(ApkRelease)
        .where(ApkRelease.published_at.is_not(None))
        .order_by(ApkRelease.published_at.desc())
        .limit(1)
    )
    if release is None or release.published_at is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No signed release is published")
    return ApkReleaseResponse(
        version=release.version,
        apk_url=release.apk_url,
        github_release_url=release.github_release_url,
        sha256=release.sha256,
        minimum_android=release.minimum_android,
        release_notes=release.release_notes,
        published_at=release.published_at,
    )
