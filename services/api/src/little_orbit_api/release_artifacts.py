"""Locate and verify immutable APK bytes stored outside the repository."""

from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest
from os import stat_result
from pathlib import Path
from urllib.parse import urlsplit

APK_MEDIA_TYPE = "application/vnd.android.package-archive"
PUBLIC_RELEASE_HOST = "lil-orb.pax-kun.com"


class ReleaseArtifactUnavailable(RuntimeError):
    """Raised when locally hosted APK bytes are absent or fail their release record."""


@dataclass(frozen=True)
class VerifiedReleaseArtifact:
    """A release file whose size and digest match immutable published metadata."""

    path: Path
    filename: str
    stat: stat_result


def hosted_apk_url(version: str) -> str:
    """Return the one public first-party APK URL for a version."""

    return f"https://{PUBLIC_RELEASE_HOST}/api/v1/releases/{version}/apk"


def is_hosted_apk_url(value: str, version: str) -> bool:
    """Accept only the query-free HTTPS endpoint for the matching release."""

    url = urlsplit(value)
    return (
        url.scheme == "https"
        and url.hostname == PUBLIC_RELEASE_HOST
        and url.port in (None, 443)
        and url.username is None
        and url.password is None
        and url.path == f"/api/v1/releases/{version}/apk"
        and not url.query
        and not url.fragment
    )


def verify_release_artifact(
    storage_root: Path,
    version: str,
    expected_size: int,
    expected_sha256: str,
) -> VerifiedReleaseArtifact:
    """Verify the deterministic release file before it is published or served."""

    filename = f"little-orbit-{version}.apk"
    path = storage_root / filename
    try:
        before = path.stat()
        if not path.is_file() or before.st_size != expected_size:
            raise ReleaseArtifactUnavailable("release artifact size mismatch")
        digest = _sha256(path)
        after = path.stat()
    except OSError as error:
        raise ReleaseArtifactUnavailable("release artifact unavailable") from error
    if before.st_mtime_ns != after.st_mtime_ns or before.st_size != after.st_size:
        raise ReleaseArtifactUnavailable("release artifact changed during verification")
    if not compare_digest(digest, expected_sha256):
        raise ReleaseArtifactUnavailable("release artifact checksum mismatch")
    return VerifiedReleaseArtifact(path=path, filename=filename, stat=after)


def _sha256(path: Path) -> str:
    """Hash one file without loading the APK into process memory."""

    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
