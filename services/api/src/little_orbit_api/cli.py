"""Explicit local-operator commands for bootstrapping owner access."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from sqlalchemy import select

from .clock import SystemClock
from .database import SessionFactory
from .models import Account, Couple, CoupleMember, SecurityEvent
from .note_deduplication import classify_and_archive_duplicates
from .release_service import upsert_apk_release
from .schemas import ApkReleaseInput
from .security import normalize_email
from .together_time_service import (
    ALGORITHM_VERSION,
    reaggregate_retained_history,
    recompute_recent_proximity,
)


async def promote_admin(email: str) -> None:
    """Promote one existing verified account and record the local operation."""

    async with SessionFactory() as session:
        account = await session.scalar(
            select(Account)
            .where(Account.email_normalized == normalize_email(email))
            .with_for_update()
        )
        if account is None or account.verified_at is None or account.deleted_at is not None:
            raise RuntimeError("A verified active account with that email was not found")
        account.is_admin = True
        session.add(
            SecurityEvent(
                actor_id=account.id,
                event_type="local_admin_promotion",
                outcome="accepted",
                metadata_json={},
                created_at=SystemClock().now(),
            )
        )
        await session.commit()
    print("Verified account promoted. Complete MFA enrollment before using the console.")


async def publish_release(payload: ApkReleaseInput) -> None:
    """Publish validated GitHub release metadata from the trusted local host."""

    async with SessionFactory() as session:
        await upsert_apk_release(session, payload, updated_by=None)
        session.add(
            SecurityEvent(
                actor_id=None,
                event_type="local_apk_release_publication",
                outcome="accepted",
                metadata_json={"version": payload.version, "sha256": payload.sha256},
                created_at=SystemClock().now(),
            )
        )
        await session.commit()
    print("Signed APK release metadata published.")


async def deduplicate_notes(*, apply: bool, backup_manifest: str | None) -> None:
    """Classify exact duplicates and require a fresh encrypted backup before changes."""

    if apply:
        if backup_manifest is None:
            raise RuntimeError("--backup-manifest is required with --apply")
        _verify_backup_manifest(Path(backup_manifest))
    async with SessionFactory() as session:
        report = await classify_and_archive_duplicates(session, apply=apply)
    print(json.dumps(report.__dict__, sort_keys=True))


async def reaggregate_together_time(*, apply: bool, backup_manifest: str | None) -> None:
    """Rebuild only the raw-evidence window after migration, never historical gaps."""

    if apply:
        if backup_manifest is None:
            raise RuntimeError("--backup-manifest is required with --apply")
        _verify_backup_manifest(Path(backup_manifest))
    async with SessionFactory() as session:
        couple_ids = list(
            await session.scalars(
                select(Couple.id).where(Couple.ended_at.is_(None))
            )
        )
        rebuilt = 0
        if apply:
            for couple_id in couple_ids:
                couple = await session.scalar(
                    select(Couple).where(Couple.id == couple_id).with_for_update()
                )
                if couple is None or couple.ended_at is not None:
                    continue
                members = list(
                    await session.scalars(
                        select(CoupleMember.account_id)
                        .where(
                            CoupleMember.couple_id == couple.id,
                            CoupleMember.left_at.is_(None),
                        )
                        .order_by(CoupleMember.account_id)
                    )
                )
                if len(members) != 2:
                    continue
                if couple.proximity_algorithm_version < ALGORITHM_VERSION:
                    await recompute_recent_proximity(session, couple, members, [])
                await reaggregate_retained_history(session, couple)
                await session.commit()
                rebuilt += 1
    print(json.dumps({"eligible_couples": len(couple_ids), "rebuilt": rebuilt}))


def _verify_backup_manifest(path: Path) -> None:
    """Verify the encrypted PostgreSQL artifact named by its privacy sidecar."""

    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    encrypted = path.parent / str(payload.get("encrypted_file", ""))
    if payload.get("raw_location_rows_included") is not False:
        raise RuntimeError("backup may include raw location rows")
    if payload.get("device_health_rows_included") is not False:
        raise RuntimeError("backup may include device health rows")
    if not encrypted.is_file():
        raise RuntimeError("encrypted backup file is missing")
    digest = hashlib.sha256(encrypted.read_bytes()).hexdigest()
    if digest != payload.get("encrypted_sha256"):
        raise RuntimeError("encrypted backup checksum does not match")


def main() -> None:
    """Parse and run an explicit local administrative command."""

    _dispatch(_command_parser().parse_args())


def _command_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="little-orbit-admin")
    subcommands = parser.add_subparsers(dest="command", required=True)
    promote = subcommands.add_parser("promote-admin")
    promote.add_argument("email")
    release = subcommands.add_parser("publish-release")
    release.add_argument("--version", required=True)
    release.add_argument("--version-code", required=True, type=int)
    release.add_argument("--apk-url", required=True)
    release.add_argument("--github-release-url", required=True)
    release.add_argument("--sha256", required=True)
    release.add_argument("--size-bytes", required=True, type=int)
    release.add_argument("--package-name", default="com.littleorbit.mobile")
    release.add_argument("--signer-sha256", required=True)
    release.add_argument("--wear-apk-url")
    release.add_argument("--wear-sha256")
    release.add_argument("--wear-size-bytes", type=int)
    release.add_argument("--wear-package-name")
    release.add_argument("--wear-version-code", type=int)
    release.add_argument("--wear-minimum-android", type=int)
    release.add_argument("--minimum-android", required=True, type=int)
    release.add_argument("--minimum-supported-version-code", default=1, type=int)
    release.add_argument("--required-after")
    release.add_argument("--release-notes", required=True)
    dedupe = subcommands.add_parser("deduplicate-notes")
    dedupe.add_argument("--apply", action="store_true")
    dedupe.add_argument("--backup-manifest")
    reaggregate = subcommands.add_parser("reaggregate-together-time")
    reaggregate.add_argument("--apply", action="store_true")
    reaggregate.add_argument("--backup-manifest")
    return parser


def _dispatch(arguments: argparse.Namespace) -> None:
    if arguments.command == "promote-admin":
        asyncio.run(promote_admin(arguments.email))
    if arguments.command == "publish-release":
        asyncio.run(publish_release(_release_payload(arguments)))
    if arguments.command == "deduplicate-notes":
        asyncio.run(
            deduplicate_notes(
                apply=arguments.apply,
                backup_manifest=arguments.backup_manifest,
            )
        )
    if arguments.command == "reaggregate-together-time":
        asyncio.run(
            reaggregate_together_time(
                apply=arguments.apply,
                backup_manifest=arguments.backup_manifest,
            )
        )


def _release_payload(arguments: argparse.Namespace) -> ApkReleaseInput:
    return ApkReleaseInput(
        version=arguments.version,
        version_code=arguments.version_code,
        apk_url=arguments.apk_url,
        github_release_url=arguments.github_release_url,
        sha256=arguments.sha256,
        size_bytes=arguments.size_bytes,
        package_name=arguments.package_name,
        signer_sha256=arguments.signer_sha256,
        wear_apk_url=arguments.wear_apk_url,
        wear_sha256=arguments.wear_sha256,
        wear_size_bytes=arguments.wear_size_bytes,
        wear_package_name=arguments.wear_package_name,
        wear_version_code=arguments.wear_version_code,
        wear_minimum_android=arguments.wear_minimum_android,
        minimum_android=arguments.minimum_android,
        minimum_supported_version_code=arguments.minimum_supported_version_code,
        required_after=arguments.required_after,
        release_notes=arguments.release_notes,
        publish=True,
    )


if __name__ == "__main__":
    main()
