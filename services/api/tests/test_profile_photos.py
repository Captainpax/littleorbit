"""Profile-photo normalization, authorization ordering, and caching tests."""

from io import BytesIO
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from PIL import Image

from little_orbit_api.models import Account
from little_orbit_api.profile_images import InvalidProfileImage, normalize_profile_image
from little_orbit_api.profile_models import AccountProfilePhoto
from little_orbit_api.routes.profile_photos import (
    _photo_response,
    get_partner_profile_photo,
)


def _png_bytes(width: int = 640, height: int = 480) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), (255, 113, 119)).save(output, format="PNG")
    return output.getvalue()


def test_normalization_strips_input_format_and_creates_bounded_square_variants() -> None:
    normalized = normalize_profile_image(_png_bytes(), "image/png")

    with Image.open(BytesIO(normalized.image_webp)) as full:
        assert full.format == "WEBP"
        assert full.size == (512, 512)
        assert not full.getexif()
    with Image.open(BytesIO(normalized.thumbnail_webp)) as thumbnail:
        assert thumbnail.size == (128, 128)
    assert len(normalized.sha256) == 64
    assert len(normalized.thumbnail_sha256) == 64


@pytest.mark.parametrize("media_type", ["image/gif", "text/plain", ""])
def test_normalization_rejects_unsupported_media_types(media_type: str) -> None:
    with pytest.raises(InvalidProfileImage):
        normalize_profile_image(_png_bytes(), media_type)


def test_photo_response_honors_private_etag_revalidation() -> None:
    digest = "a" * 64
    photo = SimpleNamespace(
        image_webp=b"image",
        thumbnail_webp=b"thumb",
        sha256=digest,
        thumbnail_sha256="b" * 64,
    )

    response = _photo_response(
        cast(AccountProfilePhoto, photo), f'"{digest}"', thumbnail=False
    )

    assert response.status_code == 304
    assert response.headers["cache-control"] == "private, max-age=300"
    assert response.headers["vary"] == "Authorization"


@pytest.mark.asyncio
async def test_partner_authorization_precedes_photo_lookup() -> None:
    session = AsyncMock()
    session.scalar.return_value = None
    actor = SimpleNamespace(id=uuid4())

    with pytest.raises(HTTPException) as failure:
        await get_partner_profile_photo(None, cast(Account, actor), session)

    assert failure.value.status_code == 404
    session.get.assert_not_awaited()
