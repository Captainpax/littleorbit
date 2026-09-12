"""Bounded, metadata-free profile image normalization."""

import warnings
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_DECODED_PIXELS = 20_000_000
MAX_NORMALIZED_BYTES = 512 * 1024
MAX_THUMBNAIL_BYTES = 64 * 1024
SUPPORTED_MEDIA_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})

Image.MAX_IMAGE_PIXELS = MAX_DECODED_PIXELS


class InvalidProfileImage(ValueError):
    """Raised when uploaded bytes cannot become one safe static profile image."""


@dataclass(frozen=True)
class NormalizedProfileImage:
    """Server-owned full and Wear thumbnail encodings with stable hashes."""

    image_webp: bytes
    thumbnail_webp: bytes
    sha256: str
    thumbnail_sha256: str


def normalize_profile_image(raw: bytes, media_type: str) -> NormalizedProfileImage:
    """Decode one bounded image, strip metadata, crop it square, and encode WebP."""

    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise InvalidProfileImage("Profile photo must be JPEG, PNG, or WebP")
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        raise InvalidProfileImage("Profile photo must be between 1 byte and 5 MiB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if getattr(source, "is_animated", False):
                    raise InvalidProfileImage("Animated profile photos are not supported")
                source.load()
                if source.width * source.height > MAX_DECODED_PIXELS:
                    raise InvalidProfileImage("Profile photo dimensions are too large")
                oriented = ImageOps.exif_transpose(source).convert("RGB")
                image = ImageOps.fit(oriented, (512, 512), method=Image.Resampling.LANCZOS)
                thumbnail = ImageOps.fit(oriented, (128, 128), method=Image.Resampling.LANCZOS)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise InvalidProfileImage("Profile photo dimensions are too large") from error
    except (OSError, UnidentifiedImageError) as error:
        raise InvalidProfileImage("Profile photo is not a valid image") from error
    full_bytes = _encode(image, quality=82)
    thumb_bytes = _encode(thumbnail, quality=78)
    if len(full_bytes) > MAX_NORMALIZED_BYTES or len(thumb_bytes) > MAX_THUMBNAIL_BYTES:
        raise InvalidProfileImage("Normalized profile photo is too large")
    return NormalizedProfileImage(
        image_webp=full_bytes,
        thumbnail_webp=thumb_bytes,
        sha256=sha256(full_bytes).hexdigest(),
        thumbnail_sha256=sha256(thumb_bytes).hexdigest(),
    )


def _encode(image: Image.Image, quality: int) -> bytes:
    target = BytesIO()
    image.save(target, format="WEBP", quality=quality, method=6, exif=b"")
    return target.getvalue()
