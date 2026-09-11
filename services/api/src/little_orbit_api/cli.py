"""Explicit local-operator commands for bootstrapping owner access."""

import argparse
import asyncio

from sqlalchemy import select

from .clock import SystemClock
from .database import SessionFactory
from .models import Account, SecurityEvent
from .release_service import upsert_apk_release
from .schemas import ApkReleaseInput
from .security import normalize_email


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


def main() -> None:
    """Parse and run an explicit local administrative command."""

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
    release.add_argument("--minimum-android", required=True, type=int)
    release.add_argument("--minimum-supported-version-code", default=1, type=int)
    release.add_argument("--required-after")
    release.add_argument("--release-notes", required=True)
    arguments = parser.parse_args()
    if arguments.command == "promote-admin":
        asyncio.run(promote_admin(arguments.email))
    if arguments.command == "publish-release":
        payload = ApkReleaseInput(
            version=arguments.version,
            version_code=arguments.version_code,
            apk_url=arguments.apk_url,
            github_release_url=arguments.github_release_url,
            sha256=arguments.sha256,
            size_bytes=arguments.size_bytes,
            package_name=arguments.package_name,
            signer_sha256=arguments.signer_sha256,
            minimum_android=arguments.minimum_android,
            minimum_supported_version_code=arguments.minimum_supported_version_code,
            required_after=arguments.required_after,
            release_notes=arguments.release_notes,
            publish=True,
        )
        asyncio.run(publish_release(payload))


if __name__ == "__main__":
    main()
