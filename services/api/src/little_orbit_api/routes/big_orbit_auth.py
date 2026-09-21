"""Device-bound authentication and enrollment for the Big Orbit Android app."""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..admin_device_models import AdminDevice, AdminDeviceSession
from ..big_orbit_auth import (
    approve_device,
    authenticate_admin,
    consume_signed_challenge,
    create_device_challenge,
    create_enrollment_device,
    credential_valid,
    issue_device_session,
)
from ..big_orbit_dependencies import BigOrbitPrincipal, current_big_orbit_admin
from ..big_orbit_schemas import (
    AdminDeviceView,
    BigOrbitSessionRequest,
    BigOrbitSessionResponse,
    DeviceChallengeRequest,
    DeviceChallengeResponse,
    DeviceEnrollmentConfirm,
    DeviceEnrollmentResult,
    DeviceSessionRequest,
)
from ..clock import SystemClock
from ..config import Settings, get_settings
from ..database import session_scope
from ..dependencies import current_admin, request_client_ip
from ..models import Account, SecurityEvent, Session
from ..rate_limit import consume_rate_limits, request_rules
from ..schemas import PublicMessage
from ..security import hash_token, normalize_email

router = APIRouter(prefix="/v2/admin", tags=["big-orbit-auth"])


@router.post("/device-challenges", response_model=DeviceChallengeResponse)
async def device_challenge(
    payload: DeviceChallengeRequest,
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> DeviceChallengeResponse:
    """Return an indistinguishable real or decoy challenge for one device ID."""

    await _rate_limit("big-orbit-challenge", client_ip, str(payload.device_id), settings)
    device = await session.scalar(
        select(AdminDevice).where(
            AdminDevice.id == payload.device_id,
            AdminDevice.approved_at.is_not(None),
            AdminDevice.revoked_at.is_(None),
        )
    )
    response = await create_device_challenge(session, device, "session", settings)
    await session.commit()
    return response


@router.post("/session", response_model=BigOrbitSessionResponse)
async def password_session(
    payload: BigOrbitSessionRequest,
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> BigOrbitSessionResponse:
    """Authenticate MFA and bind the resulting session to one exact device key."""

    email = normalize_email(str(payload.email))
    await _rate_limit("big-orbit-session", client_ip, email, settings)
    account = await authenticate_admin(
        session,
        email,
        payload.password,
        payload.totp_code,
        payload.recovery_code,
        settings,
    )
    if payload.enrollment_public_key is not None and payload.device_label is not None:
        device = await create_enrollment_device(
            session,
            account,
            payload.device_label,
            payload.enrollment_public_key,
        )
        challenge = await create_device_challenge(session, device, "enrollment", settings)
        enrollment_required = True
    else:
        if payload.challenge_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Device proof is incomplete")
        device = await _returning_device(session, account, payload)
        await consume_signed_challenge(
            session,
            device,
            payload.challenge_id,
            payload.challenge or "",
            payload.signature or "",
            "session",
            settings,
        )
        challenge = None
        enrollment_required = False
    issued = await issue_device_session(session, account, device, settings)
    session.add(_event(account.id, "big_orbit_session", "accepted"))
    await session.commit()
    return BigOrbitSessionResponse(
        access_token=issued.token,
        expires_at=issued.expires_at,
        account_id=account.id,
        device_id=device.id,
        enrollment_required=enrollment_required,
        enrollment_challenge=challenge,
    )


@router.post(
    "/devices/{device_id}/confirm",
    response_model=DeviceEnrollmentResult,
)
async def confirm_device(
    device_id: UUID,
    payload: DeviceEnrollmentConfirm,
    admin: Account = Depends(current_admin),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> DeviceEnrollmentResult:
    """Confirm a pending key only from the short session mapped to that device."""

    device = await _authorized_pending_device(
        session,
        admin.id,
        device_id,
        authorization,
        settings,
    )
    await consume_signed_challenge(
        session,
        device,
        payload.challenge_id,
        payload.challenge,
        payload.signature,
        "enrollment",
        settings,
    )
    credential, expires = approve_device(device, settings)
    session.add(_event(admin.id, "big_orbit_device", "enrolled"))
    await session.commit()
    return DeviceEnrollmentResult(
        device_id=device.id,
        device_credential=credential,
        credential_expires_at=expires,
    )


@router.post("/device-session", response_model=BigOrbitSessionResponse)
async def device_session(
    payload: DeviceSessionRequest,
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> BigOrbitSessionResponse:
    """Rotate a short session for an approved key and stored device credential."""

    await _rate_limit("big-orbit-device-session", client_ip, str(payload.device_id), settings)
    account, device = await _locked_device_principal(
        session, payload.device_id, payload.device_credential, settings
    )
    await consume_signed_challenge(
        session,
        device,
        payload.challenge_id,
        payload.challenge,
        payload.signature,
        "session",
        settings,
    )
    issued = await issue_device_session(session, account, device, settings)
    await session.commit()
    return BigOrbitSessionResponse(
        access_token=issued.token,
        expires_at=issued.expires_at,
        account_id=account.id,
        device_id=device.id,
        enrollment_required=False,
    )


async def _locked_device_principal(
    session: AsyncSession,
    device_id: UUID,
    credential: str,
    settings: Settings,
) -> tuple[Account, AdminDevice]:
    """Lock the owning account before its device so session rotation cannot race."""

    owner_id = await session.scalar(
        select(AdminDevice.account_id).where(AdminDevice.id == device_id)
    )
    if owner_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Device credentials are invalid")
    account = await session.scalar(
        select(Account)
        .where(
            Account.id == owner_id,
            Account.is_admin.is_(True),
            Account.verified_at.is_not(None),
            Account.suspended_at.is_(None),
            Account.deleted_at.is_(None),
        )
        .with_for_update()
    )
    device = await session.scalar(
        select(AdminDevice)
        .where(
            AdminDevice.id == device_id,
            AdminDevice.account_id == owner_id,
        )
        .with_for_update()
    )
    if (
        account is None
        or device is None
        or not credential_valid(device, credential, settings)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Device credentials are invalid")
    return account, device


@router.get("/devices", response_model=list[AdminDeviceView])
async def devices(
    principal: BigOrbitPrincipal = Depends(current_big_orbit_admin),
    session: AsyncSession = Depends(session_scope),
) -> list[AdminDeviceView]:
    """List only devices belonging to the authenticated administrator."""

    records = list(
        await session.scalars(
            select(AdminDevice)
            .where(AdminDevice.account_id == principal.account.id)
            .order_by(AdminDevice.created_at.desc())
        )
    )
    return [AdminDeviceView.model_validate(record, from_attributes=True) for record in records]


@router.delete("/devices/{device_id}", response_model=PublicMessage)
async def revoke_device(
    device_id: UUID,
    principal: BigOrbitPrincipal = Depends(current_big_orbit_admin),
    session: AsyncSession = Depends(session_scope),
) -> PublicMessage:
    """Revoke one owned device and every short session bound to it."""

    device = await session.scalar(
        select(AdminDevice)
        .where(
            AdminDevice.id == device_id,
            AdminDevice.account_id == principal.account.id,
        )
        .with_for_update()
    )
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device is unavailable")
    now = SystemClock().now()
    device.revoked_at = now
    device.credential_hash = None
    device.credential_expires_at = None
    session_ids = select(AdminDeviceSession.session_id).where(
        AdminDeviceSession.device_id == device.id
    )
    active = await session.scalars(select(Session).where(Session.id.in_(session_ids)))
    for item in active:
        item.revoked_at = now
    session.add(_event(principal.account.id, "big_orbit_device", "revoked"))
    await session.commit()
    return PublicMessage(message="Big Orbit device revoked.")


async def _returning_device(
    session: AsyncSession,
    account: Account,
    payload: BigOrbitSessionRequest,
) -> AdminDevice:
    device = await session.scalar(
        select(AdminDevice)
        .where(
            AdminDevice.id == payload.device_id,
            AdminDevice.account_id == account.id,
            AdminDevice.approved_at.is_not(None),
            AdminDevice.revoked_at.is_(None),
        )
        .with_for_update()
    )
    if device is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Administrator credentials are invalid")
    return device


async def _authorized_pending_device(
    session: AsyncSession,
    account_id: UUID,
    device_id: UUID,
    authorization: str | None,
    settings: Settings,
) -> AdminDevice:
    # current_admin already authenticated the bearer. Resolve its exact session before
    # touching the pending device so another administrator cannot confirm it.
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Device enrollment is unavailable")
    digest = hash_token(authorization[7:], settings.token_pepper.get_secret_value())
    token_sessions = (
        select(AdminDeviceSession.device_id)
        .join(Session, Session.id == AdminDeviceSession.session_id)
        .where(
            Session.account_id == account_id,
            Session.token_hash == digest,
            Session.revoked_at.is_(None),
            Session.expires_at > SystemClock().now(),
        )
    )
    mapped = set(await session.scalars(token_sessions))
    if device_id not in mapped:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Device enrollment is unavailable")
    device = await session.scalar(
        select(AdminDevice)
        .where(AdminDevice.id == device_id, AdminDevice.account_id == account_id)
        .with_for_update()
    )
    if device is None or device.approved_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Device enrollment is unavailable")
    return device


async def _rate_limit(
    action: str,
    client_ip: str,
    subject: str,
    settings: Settings,
) -> None:
    decision = await consume_rate_limits(
        request_rules(
            action,
            client_ip,
            subject,
            ip_limit=settings.admin_auth_ip_per_15_minutes,
            subject_limit=settings.admin_auth_subject_per_15_minutes,
            window=timedelta(minutes=15),
        ),
        settings=settings,
    )
    if not decision.allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Administrator authentication is temporarily unavailable",
            headers={"Retry-After": "900"},
        )


def _event(actor_id: UUID, event_type: str, outcome: str) -> SecurityEvent:
    return SecurityEvent(
        actor_id=actor_id,
        event_type=event_type,
        outcome=outcome,
        metadata_json={},
        created_at=SystemClock().now(),
    )
