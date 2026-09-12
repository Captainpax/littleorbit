"""Authenticated profile identity and partner-authorized photo delivery."""

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..database import session_scope
from ..dependencies import current_account
from ..models import Account, CoupleMember
from ..profile_images import MAX_UPLOAD_BYTES, InvalidProfileImage, normalize_profile_image
from ..profile_models import AccountProfilePhoto
from ..profile_schemas import (
    OrbitProfilePerson,
    OrbitProfileResponse,
    ProfilePhotoMetadata,
)

router = APIRouter(prefix="/v1", tags=["profile"])


async def _read_bounded_upload(request: Request) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Profile photo is too large")
        chunks.append(chunk)
    return b"".join(chunks)


def _metadata(photo: AccountProfilePhoto | None) -> ProfilePhotoMetadata | None:
    if photo is None:
        return None
    return ProfilePhotoMetadata(
        revision=photo.revision,
        sha256=photo.sha256,
        updated_at=photo.updated_at,
    )


async def _active_partner(
    session: AsyncSession, actor_id: UUID
) -> Account | None:
    membership = await session.scalar(
        select(CoupleMember).where(
            CoupleMember.account_id == actor_id,
            CoupleMember.left_at.is_(None),
        )
    )
    if membership is None:
        return None
    return cast(
        Account | None,
        await session.scalar(
            select(Account)
            .join(CoupleMember, CoupleMember.account_id == Account.id)
            .where(
                CoupleMember.couple_id == membership.couple_id,
                CoupleMember.left_at.is_(None),
                Account.id != actor_id,
                Account.deleted_at.is_(None),
            )
        )
    )


async def _lock_photo_owner(session: AsyncSession, actor_id: UUID) -> None:
    """Serialize photo replacement and deletion even when no photo row exists yet."""

    await session.execute(
        select(Account.id).where(Account.id == actor_id).with_for_update()
    )


@router.get("/account/orbit-profile", response_model=OrbitProfileResponse)
async def orbit_profile(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> OrbitProfileResponse:
    """Return only display identities authorized by the current pairing."""

    own_photo = await session.get(AccountProfilePhoto, actor.id)
    partner = await _active_partner(session, actor.id)
    partner_photo = await session.get(AccountProfilePhoto, partner.id) if partner else None
    return OrbitProfileResponse(
        me=OrbitProfilePerson(display_name=actor.display_name, photo=_metadata(own_photo)),
        partner=(
            OrbitProfilePerson(display_name=partner.display_name, photo=_metadata(partner_photo))
            if partner
            else None
        ),
    )


@router.put("/account/profile-photo", response_model=ProfilePhotoMetadata)
async def put_profile_photo(
    request: Request,
    content_type: str | None = Header(default=None),
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> ProfilePhotoMetadata:
    """Normalize and replace the authenticated account's private profile photo."""

    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    try:
        normalized = normalize_profile_image(await _read_bounded_upload(request), media_type)
    except InvalidProfileImage as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    now = SystemClock().now()
    await _lock_photo_owner(session, actor.id)
    existing = await session.get(AccountProfilePhoto, actor.id, with_for_update=True)
    if existing is not None and existing.sha256 == normalized.sha256:
        metadata = _metadata(existing)
        assert metadata is not None
        return metadata
    revision = 1 if existing is None else existing.revision + 1
    values = {
        "image_webp": normalized.image_webp,
        "thumbnail_webp": normalized.thumbnail_webp,
        "sha256": normalized.sha256,
        "thumbnail_sha256": normalized.thumbnail_sha256,
        "revision": revision,
        "updated_at": now,
    }
    if existing is None:
        existing = AccountProfilePhoto(account_id=actor.id, **values)
        session.add(existing)
    else:
        for key, value in values.items():
            setattr(existing, key, value)
    await session.commit()
    metadata = _metadata(existing)
    assert metadata is not None
    return metadata


@router.delete("/account/profile-photo", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile_photo(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> Response:
    """Idempotently remove the authenticated account's profile photo."""

    await _lock_photo_owner(session, actor.id)
    existing = await session.get(AccountProfilePhoto, actor.id, with_for_update=True)
    if existing is not None:
        await session.delete(existing)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/account/profile-photo")
async def get_profile_photo(
    if_none_match: str | None = Header(default=None),
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
    thumbnail: bool = Query(default=False),
) -> Response:
    """Return the authenticated account's normalized photo with private caching."""

    photo = await session.get(AccountProfilePhoto, actor.id)
    return _photo_response(photo, if_none_match, thumbnail=thumbnail)


@router.get("/couple/current/partner-profile-photo")
async def get_partner_profile_photo(
    if_none_match: str | None = Header(default=None),
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
    thumbnail: bool = Query(default=False),
) -> Response:
    """Authorize the active pairing before looking up the partner's thumbnail."""

    partner = await _active_partner(session, actor.id)
    if partner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile photo is unavailable")
    photo = await session.get(AccountProfilePhoto, partner.id)
    return _photo_response(photo, if_none_match, thumbnail=thumbnail)


def _photo_response(
    photo: AccountProfilePhoto | None, if_none_match: str | None, *, thumbnail: bool
) -> Response:
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile photo is unavailable")
    digest = photo.thumbnail_sha256 if thumbnail else photo.sha256
    etag = f'"{digest}"'
    headers = {"Cache-Control": "private, max-age=300", "ETag": etag, "Vary": "Authorization"}
    if if_none_match == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    body = photo.thumbnail_webp if thumbnail else photo.image_webp
    return Response(content=body, media_type="image/webp", headers=headers)
