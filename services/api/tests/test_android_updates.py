"""Release-contract and Android compatibility regression tests."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from little_orbit_api.client_compatibility import (
    is_mobile_http_path,
    supplied_version_code,
    update_required,
)
from little_orbit_api.models import ApkRelease
from little_orbit_api.release_service import PublishedReleaseImmutable, upsert_apk_release
from little_orbit_api.schemas import ApkReleaseInput

SIGNER = "43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337"


def release_input(**overrides: object) -> ApkReleaseInput:
    """Build one canonical release payload with explicit safe defaults."""

    values: dict[str, object] = {
        "version": "1.0.0-rc.3",
        "version_code": 3,
        "apk_url": (
            "https://github.com/Captainpax/littleorbit/releases/download/"
            "v1.0.0-rc.3/little-orbit-1.0.0-rc.3.apk"
        ),
        "github_release_url": (
            "https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0-rc.3"
        ),
        "sha256": "a" * 64,
        "size_bytes": 1024,
        "package_name": "com.littleorbit.mobile",
        "signer_sha256": SIGNER,
        "minimum_android": 29,
        "minimum_supported_version_code": 1,
        "required_after": None,
        "release_notes": "Safer updates.",
        "publish": True,
    }
    values.update(overrides)
    return ApkReleaseInput.model_validate(values)


def test_release_contract_accepts_canonical_rc3() -> None:
    release = release_input(required_after=datetime(2026, 10, 1, tzinfo=UTC))
    assert release.version_code == 3
    assert release.package_name == "com.littleorbit.mobile"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("apk_url", "http://github.com/Captainpax/littleorbit/releases/download/v1.0.0-rc.3/x.apk"),
        ("apk_url", "https://example.com/Captainpax/littleorbit/releases/download/v1.0.0-rc.3/x.apk"),
        ("github_release_url", "https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0-rc.2"),
        ("package_name", "com.example.fake"),
        ("minimum_supported_version_code", 4),
        ("required_after", "2026-10-01T12:00:00"),
    ],
)
def test_release_contract_rejects_unsafe_authority(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        release_input(**{field: value})


def test_compatibility_gate_is_inactive_without_scheduled_floor() -> None:
    assert not update_required(None, None)
    assert not update_required(1, None)


def test_compatibility_gate_rejects_missing_and_old_android_versions() -> None:
    assert update_required(None, 3)
    assert update_required(2, 3)
    assert not update_required(3, 3)
    assert supplied_version_code("android", "3") == 3
    assert supplied_version_code("web", "3") is None
    assert supplied_version_code("android", "-1") is None


def test_only_installed_client_routes_are_gated() -> None:
    assert is_mobile_http_path("/v1/auth/login")
    assert is_mobile_http_path("/v1/notes/00000000-0000-0000-0000-000000000000")
    assert not is_mobile_http_path("/v1/auth/register")
    assert not is_mobile_http_path("/v1/releases/current")
    assert not is_mobile_http_path("/v1/admin/session")


def published_record(payload: ApkReleaseInput) -> ApkRelease:
    """Create the exact persisted shape needed by the immutable-service tests."""

    return cast(
        ApkRelease,
        SimpleNamespace(
            version=payload.version,
            version_code=payload.version_code,
            apk_url=str(payload.apk_url),
            github_release_url=str(payload.github_release_url),
            sha256=payload.sha256,
            size_bytes=payload.size_bytes,
            package_name=payload.package_name,
            signer_sha256=payload.signer_sha256,
            minimum_android=payload.minimum_android,
            minimum_supported_version_code=payload.minimum_supported_version_code,
            required_after=payload.required_after,
            release_notes=payload.release_notes,
            published_at=datetime(2026, 9, 12, tzinfo=UTC),
        ),
    )


@pytest.mark.asyncio
async def test_exact_published_release_retry_is_idempotent() -> None:
    payload = release_input()
    record = published_record(payload)
    session = AsyncMock()
    session.scalar.return_value = record

    result = await upsert_apk_release(session, payload, updated_by=None)

    assert result is record
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_published_release_cannot_be_mutated_or_unpublished() -> None:
    original = release_input()
    session = AsyncMock()
    session.scalar.return_value = published_record(original)

    with pytest.raises(PublishedReleaseImmutable):
        await upsert_apk_release(
            session,
            release_input(release_notes="Changed after publication."),
            updated_by=None,
        )
    with pytest.raises(PublishedReleaseImmutable):
        await upsert_apk_release(session, release_input(publish=False), updated_by=None)
