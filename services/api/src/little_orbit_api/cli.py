"""Explicit local-operator commands for bootstrapping owner access."""

import argparse
import asyncio

from sqlalchemy import select

from .clock import SystemClock
from .database import SessionFactory
from .models import Account, SecurityEvent
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


def main() -> None:
    """Parse and run an explicit local administrative command."""

    parser = argparse.ArgumentParser(prog="little-orbit-admin")
    subcommands = parser.add_subparsers(dest="command", required=True)
    promote = subcommands.add_parser("promote-admin")
    promote.add_argument("email")
    arguments = parser.parse_args()
    if arguments.command == "promote-admin":
        asyncio.run(promote_admin(arguments.email))


if __name__ == "__main__":
    main()
