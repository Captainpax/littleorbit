"""Partner-assigned, relationship-scoped avatar storage and delivery."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..couple_access import active_member, lock_couple
from ..database import session_scope
from ..dependencies import current_account
from ..models import Account, CoupleMember
from ..profile_images import MAX_UPLOAD_BYTES, InvalidProfileImage, normalize_profile_image
from ..profile_models import RelationshipAvatar
from ..profile_schemas import OrbitProfilePerson, OrbitProfileResponse, ProfilePhotoMetadata

router = APIRouter(prefix="/v1", tags=["profile"])


async def _read_bounded_upload(request: Request) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Avatar is too large")
        chunks.append(chunk)
    return b"".join(chunks)


def _metadata(photo: RelationshipAvatar | None) -> ProfilePhotoMetadata | None:
    if photo is None:
        return None
    return ProfilePhotoMetadata(
        revision=photo.revision,
        sha256=photo.sha256,
        updated_at=photo.updated_at,
    )


async def _partner_id(session: AsyncSession, couple_id: UUID, actor_id: UUID) -> UUID:
    partner_id = await session.scalar(
        select(CoupleMember.account_id).where(
            CoupleMember.couple_id == couple_id,
            CoupleMember.account_id != actor_id,
            CoupleMember.left_at.is_(None),
        )
    )
    if partner_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Avatar is unavailable")
    return partner_id


async def _avatar(
    session: AsyncSession, couple_id: UUID, subject_id: UUID, *, lock: bool = False
) -> RelationshipAvatar | None:
    statement = select(RelationshipAvatar).where(
        RelationshipAvatar.couple_id == couple_id,
        RelationshipAvatar.subject_account_id == subject_id,
    )
    if lock:
        statement = statement.with_for_update()
    return await session.scalar(statement)


@router.get("/account/orbit-profile", response_model=OrbitProfileResponse)
async def orbit_profile(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> OrbitProfileResponse:
    """Return identities and the two avatars authorized by the active pairing."""

    member = await active_member(session, actor.id)
    partner_id = await _partner_id(session, member.couple_id, actor.id)
    partner = await session.get(Account, partner_id)
    own_avatar = await _avatar(session, member.couple_id, actor.id)
    partner_avatar = await _avatar(session, member.couple_id, partner_id)
    return OrbitProfileResponse(
        me=OrbitProfilePerson(display_name=actor.display_name, photo=_metadata(own_avatar)),
        partner=(
            OrbitProfilePerson(display_name=partner.display_name, photo=_metadata(partner_avatar))
            if partner is not None
            else None
        ),
    )


@router.put("/couple/current/partner-avatar", response_model=ProfilePhotoMetadata)
async def put_partner_avatar(
    request: Request,
    content_type: str | None = Header(default=None),
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> ProfilePhotoMetadata:
    """Assign a sanitized image to the caller's current partner."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    partner_id = await _partner_id(session, member.couple_id, actor.id)
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    try:
        image = normalize_profile_image(await _read_bounded_upload(request), media_type)
    except InvalidProfileImage as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    existing = await _avatar(session, member.couple_id, partner_id, lock=True)
    if existing is not None and existing.sha256 == image.sha256:
        metadata = _metadata(existing)
        assert metadata is not None
        return metadata
    now = SystemClock().now()
    values = {
        "image_webp": image.image_webp,
        "thumbnail_webp": image.thumbnail_webp,
        "sha256": image.sha256,
        "thumbnail_sha256": image.thumbnail_sha256,
        "revision": 1 if existing is None else existing.revision + 1,
        "updated_at": now,
    }
    if existing is None:
        existing = RelationshipAvatar(
            couple_id=member.couple_id,
            subject_account_id=partner_id,
            assigned_by_account_id=actor.id,
            **values,
        )
        session.add(existing)
    else:
        for key, value in values.items():
            setattr(existing, key, value)
    await session.commit()
    metadata = _metadata(existing)
    assert metadata is not None
    return metadata


@router.delete("/couple/current/partner-avatar", status_code=status.HTTP_204_NO_CONTENT)
async def delete_partner_avatar(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> Response:
    """Remove only the avatar that the caller assigned to their partner."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    partner_id = await _partner_id(session, member.couple_id, actor.id)
    existing = await _avatar(session, member.couple_id, partner_id, lock=True)
    if existing is not None:
        await session.delete(existing)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/account/profile-photo", status_code=status.HTTP_410_GONE)
async def reject_legacy_self_upload(
    actor: Account = Depends(current_account),
) -> None:
    """Reject legacy self-assignment after the partner-avatar privacy migration."""

    del actor
    raise HTTPException(status.HTTP_410_GONE, "Your partner chooses your avatar")


@router.delete("/account/profile-photo", status_code=status.HTTP_410_GONE)
async def reject_legacy_self_delete(
    actor: Account = Depends(current_account),
) -> None:
    """Reject removal of an avatar controlled by the current partner."""

    del actor
    raise HTTPException(status.HTTP_410_GONE, "Your partner controls your avatar")


@router.get("/account/profile-photo")
async def get_profile_photo(
    if_none_match: str | None = Header(default=None),
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
    thumbnail: bool = Query(default=False),
) -> Response:
    """Return the avatar assigned to the caller by their current partner."""

    member = await active_member(session, actor.id)
    photo = await _avatar(session, member.couple_id, actor.id)
    return _photo_response(photo, if_none_match, thumbnail=thumbnail)


@router.get("/couple/current/partner-profile-photo")
async def get_partner_profile_photo(
    if_none_match: str | None = Header(default=None),
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
    thumbnail: bool = Query(default=False),
) -> Response:
    """Return the avatar that the caller assigned to their current partner."""

    member = await active_member(session, actor.id)
    partner_id = await _partner_id(session, member.couple_id, actor.id)
    photo = await _avatar(session, member.couple_id, partner_id)
    return _photo_response(photo, if_none_match, thumbnail=thumbnail)


def _photo_response(
    photo: RelationshipAvatar | None, if_none_match: str | None, *, thumbnail: bool
) -> Response:
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Avatar is unavailable")
    digest = photo.thumbnail_sha256 if thumbnail else photo.sha256
    etag = f'"{digest}"'
    headers = {"Cache-Control": "private, max-age=300", "ETag": etag, "Vary": "Authorization"}
    if if_none_match == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    body = photo.thumbnail_webp if thumbnail else photo.image_webp
    return Response(content=body, media_type="image/webp", headers=headers)
