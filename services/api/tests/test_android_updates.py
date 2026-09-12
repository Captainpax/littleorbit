"""Release-contract and Android compatibility regression tests."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from little_orbit_api.client_compatibility import (
    is_mobile_http_path,
    supplied_version_code,
    update_required,
)
from little_orbit_api.config import Settings, get_settings
from little_orbit_api.database import session_scope
from little_orbit_api.models import ApkRelease
from little_orbit_api.release_artifacts import (
    ReleaseArtifactUnavailable,
    hosted_apk_url,
    hosted_wear_apk_url,
    is_hosted_apk_url,
    is_hosted_wear_apk_url,
    verify_release_artifact,
    verify_wear_release_artifact,
)
from little_orbit_api.release_service import PublishedReleaseImmutable, upsert_apk_release
from little_orbit_api.routes import releases
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


def test_release_contract_accepts_matching_first_party_endpoint() -> None:
    release = release_input(apk_url=hosted_apk_url("1.0.0-rc.3"))
    assert str(release.apk_url) == hosted_apk_url("1.0.0-rc.3")
    assert is_hosted_apk_url(str(release.apk_url), release.version)


def test_rc6_requires_complete_matching_wear_metadata() -> None:
    with pytest.raises(ValidationError):
        release_input(version="1.0.0-rc.6", version_code=6)
    release = release_input(
        version="1.0.0-rc.6",
        version_code=6,
        apk_url=hosted_apk_url("1.0.0-rc.6"),
        github_release_url=(
            "https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0-rc.6"
        ),
        wear_apk_url=hosted_wear_apk_url("1.0.0-rc.6"),
        wear_sha256="b" * 64,
        wear_size_bytes=2048,
        wear_package_name="com.littleorbit.mobile",
        wear_version_code=1,
        wear_minimum_android=30,
    )
    assert is_hosted_wear_apk_url(str(release.wear_apk_url), release.version)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("apk_url", "http://github.com/Captainpax/littleorbit/releases/download/v1.0.0-rc.3/x.apk"),
        ("apk_url", "https://example.com/Captainpax/littleorbit/releases/download/v1.0.0-rc.3/x.apk"),
        ("apk_url", "https://attacker@github.com/Captainpax/littleorbit/releases/download/v1.0.0-rc.3/x.apk"),
        ("apk_url", "https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.2/apk"),
        ("apk_url", "https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.3/apk?x=1"),
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
    assert is_mobile_http_path("/v2/quizzes/today")
    assert not is_mobile_http_path("/v1/auth/register")
    assert not is_mobile_http_path("/v1/releases/current")
    assert not is_mobile_http_path("/v1/admin/session")


def test_release_artifact_requires_exact_immutable_bytes(tmp_path: Path) -> None:
    root = tmp_path
    artifact = root / "little-orbit-1.0.0-rc.4.apk"
    artifact.write_bytes(b"signed-apk-fixture")
    expected = "ade12cd72b92f20a396dceb889ba24f899806a0afd7904cb69ff815909ef2eb1"

    verified = verify_release_artifact(root, "1.0.0-rc.4", 18, expected)

    assert verified.path == artifact
    assert verified.stat.st_size == 18
    with pytest.raises(ReleaseArtifactUnavailable):
        verify_release_artifact(root, "1.0.0-rc.4", 17, expected)
    with pytest.raises(ReleaseArtifactUnavailable):
        verify_release_artifact(root, "1.0.0-rc.4", 18, "a" * 64)


def test_wear_release_artifact_uses_distinct_filename(tmp_path: Path) -> None:
    artifact = tmp_path / "little-orbit-wear-1.0.0-rc.6.apk"
    artifact.write_bytes(b"wear-apk")
    digest = "342445e5f7af9eff85cd69cdacca533068998636348ba70b073fdea3de74a275"

    verified = verify_wear_release_artifact(tmp_path, "1.0.0-rc.6", 8, digest)

    assert verified.path == artifact


def test_release_endpoint_supports_head_and_byte_range(tmp_path: Path) -> None:
    content = b"signed-apk-fixture"
    digest = "ade12cd72b92f20a396dceb889ba24f899806a0afd7904cb69ff815909ef2eb1"
    version = "1.0.0-rc.4"
    (tmp_path / f"little-orbit-{version}.apk").write_bytes(content)
    payload = release_input(
        version=version,
        version_code=4,
        apk_url=hosted_apk_url(version),
        github_release_url="https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0-rc.4",
        sha256=digest,
        size_bytes=len(content),
    )
    session = AsyncMock()
    session.scalar.return_value = published_record(payload)
    app = _release_test_app(session, tmp_path)

    with TestClient(app) as client:
        head = client.head(f"/v1/releases/{version}/apk")
        partial = client.get(
            f"/v1/releases/{version}/apk", headers={"Range": "bytes=0-5"}
        )

    assert head.status_code == 200
    assert head.headers["content-length"] == str(len(content))
    assert head.content == b""
    assert partial.status_code == 206
    assert partial.content == b"signed"
    assert partial.headers["content-range"] == "bytes 0-5/18"
    assert partial.headers["accept-ranges"] == "bytes"
    assert partial.headers["x-checksum-sha256"] == digest


def test_wear_endpoint_uses_its_own_verified_artifact(tmp_path: Path) -> None:
    phone = b"phone-apk"
    wear = b"wear-apk-fixture"
    phone_digest = "da33b1bc7e598023fde90814b6a74345c655bbaa37202985f0d86aed6de5e655"
    wear_digest = "6ae28353d99fdade4c01623835558cc610e1a64d3aaf460035df8c71c45f3d84"
    version = "1.0.0-rc.6"
    (tmp_path / f"little-orbit-{version}.apk").write_bytes(phone)
    (tmp_path / f"little-orbit-wear-{version}.apk").write_bytes(wear)
    payload = release_input(
        version=version,
        version_code=6,
        apk_url=hosted_apk_url(version),
        github_release_url=f"https://github.com/Captainpax/littleorbit/releases/tag/v{version}",
        sha256=phone_digest,
        size_bytes=len(phone),
        wear_apk_url=hosted_wear_apk_url(version),
        wear_sha256=wear_digest,
        wear_size_bytes=len(wear),
        wear_package_name="com.littleorbit.mobile",
        wear_version_code=6,
        wear_minimum_android=30,
    )
    session = AsyncMock()
    session.scalar.return_value = published_record(payload)

    with TestClient(_release_test_app(session, tmp_path)) as client:
        head = client.head(f"/v1/releases/{version}/wear-apk")
        partial = client.get(
            f"/v1/releases/{version}/wear-apk", headers={"Range": "bytes=5-7"}
        )

    assert head.status_code == 200
    assert head.headers["content-length"] == str(len(wear))
    assert partial.status_code == 206
    assert partial.content == b"apk"
    assert partial.headers["x-checksum-sha256"] == wear_digest


def _release_test_app(session: AsyncMock, storage: Path) -> FastAPI:
    """Build an isolated release router with no real database connection."""

    app = FastAPI()
    app.include_router(releases.router)

    async def fake_session() -> AsyncIterator[AsyncMock]:
        yield session

    app.dependency_overrides[session_scope] = fake_session
    app.dependency_overrides[get_settings] = lambda: Settings(release_storage_dir=storage)
    return app


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
            wear_apk_url=str(payload.wear_apk_url) if payload.wear_apk_url else None,
            wear_sha256=payload.wear_sha256,
            wear_size_bytes=payload.wear_size_bytes,
            wear_package_name=payload.wear_package_name,
            wear_version_code=payload.wear_version_code,
            wear_minimum_android=payload.wear_minimum_android,
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
