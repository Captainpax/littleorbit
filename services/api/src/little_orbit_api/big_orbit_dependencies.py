"""Authorization-first dependencies for the Big Orbit Android console."""

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .admin_device_models import AdminDevice, AdminDeviceSession
from .clock import SystemClock
from .config import Settings, get_settings
from .database import session_scope
from .models import Account, Session
from .security import hash_token


@dataclass(frozen=True)
class BigOrbitPrincipal:
    """The exact active administrator, session, and approved device."""

    account: Account
    session: Session
    device: AdminDevice


async def current_big_orbit_admin(
    authorization: str | None = Header(default=None),
    database: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> BigOrbitPrincipal:
    """Require a live MFA session bound to one non-revoked approved device."""

    if not authorization or not authorization.startswith("Bearer "):
        raise _forbidden()
    digest = hash_token(authorization[7:], settings.token_pepper.get_secret_value())
    row = (
        await database.execute(
            select(Account, Session, AdminDevice)
            .join(Session, Session.account_id == Account.id)
            .join(AdminDeviceSession, AdminDeviceSession.session_id == Session.id)
            .join(AdminDevice, AdminDevice.id == AdminDeviceSession.device_id)
            .where(
                Session.token_hash == digest,
                Session.revoked_at.is_(None),
                Session.expires_at > SystemClock().now(),
                Session.admin_mfa_verified.is_(True),
                Account.is_admin.is_(True),
                Account.verified_at.is_not(None),
                Account.suspended_at.is_(None),
                Account.deleted_at.is_(None),
                AdminDevice.approved_at.is_not(None),
                AdminDevice.revoked_at.is_(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise _forbidden()
    account, active_session, device = row
    return BigOrbitPrincipal(account, active_session, device)


def _forbidden() -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, "Big Orbit device access required")


async def current_big_orbit_account(
    principal: BigOrbitPrincipal = Depends(current_big_orbit_admin),
) -> Account:
    """Compatibility-shaped dependency for existing privacy-limited handlers."""

    return principal.account
