"""PIN-authorized Big Orbit enrollment with a privilege-separated setup token."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..big_orbit_auth import consume_signed_challenge, create_device_challenge
from ..big_orbit_bootstrap import (
    bootstrap_principal,
    bootstrap_status,
    complete_bootstrap,
    enable_bootstrap_mfa,
    start_bootstrap,
)
from ..big_orbit_schemas import (
    BootstrapCompletion,
    BootstrapDeviceConfirmResult,
    BootstrapMfaConfirm,
    BootstrapSessionRequest,
    BootstrapSessionResponse,
    BootstrapStatusResponse,
    DeviceChallengeResponse,
    DeviceEnrollmentConfirm,
)
from ..clock import SystemClock
from ..config import Settings, get_settings
from ..database import session_scope
from ..dependencies import request_client_ip
from ..rate_limit import consume_rate_limits, request_rules
from ..security import normalize_email

router = APIRouter(prefix="/v2/admin/bootstrap", tags=["big-orbit-bootstrap"])


@router.post("/session", response_model=BootstrapSessionResponse)
async def create_bootstrap_session(
    payload: BootstrapSessionRequest,
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> BootstrapSessionResponse:
    """Consume one terminal PIN and stage one unapproved P-256 device."""

    email = normalize_email(str(payload.email))
    await _rate_limit("big-orbit-bootstrap", client_ip, email, settings)
    started = await start_bootstrap(
        session,
        email,
        payload.password,
        payload.pin,
        payload.device_label,
        payload.enrollment_public_key,
        settings,
    )
    challenge = await create_device_challenge(
        session, started.device, "bootstrap", settings
    )
    await session.commit()
    return BootstrapSessionResponse(
        setup_token=started.token,
        expires_at=started.record.expires_at,
        account_id=started.account.id,
        device_id=started.device.id,
        mfa_required=started.record.mfa_required,
        challenge=challenge,
    )


@router.get("/status", response_model=BootstrapStatusResponse)
async def get_bootstrap_status(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> BootstrapStatusResponse:
    """Resume an unexpired setup without granting any administrator operation."""

    setup, account, _device = await bootstrap_principal(
        session,
        _setup_token(authorization),
        settings,
        allow_completed=True,
    )
    return await bootstrap_status(session, setup, account, settings)


@router.post("/challenge", response_model=DeviceChallengeResponse)
async def refresh_bootstrap_challenge(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> DeviceChallengeResponse:
    """Issue a fresh short key challenge while the restricted session remains valid."""

    setup, _account, device = await bootstrap_principal(
        session,
        _setup_token(authorization),
        settings,
        allow_completed=True,
    )
    challenge = await create_device_challenge(session, device, "bootstrap", settings)
    await session.commit()
    return challenge


@router.post("/device-confirm", response_model=BootstrapDeviceConfirmResult)
async def confirm_bootstrap_device(
    payload: DeviceEnrollmentConfirm,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> BootstrapDeviceConfirmResult:
    """Consume the key challenge before showing MFA material or approving the device."""

    setup, account, device = await bootstrap_principal(
        session,
        _setup_token(authorization),
        settings,
        allow_completed=True,
    )
    await consume_signed_challenge(
        session,
        device,
        payload.challenge_id,
        payload.challenge,
        payload.signature,
        "bootstrap",
        settings,
    )
    if setup.device_confirmed_at is None:
        setup.device_confirmed_at = SystemClock().now()
    if setup.mfa_required:
        response = BootstrapDeviceConfirmResult(
            completed=False,
            status=await bootstrap_status(session, setup, account, settings),
        )
    else:
        response = BootstrapDeviceConfirmResult(
            completed=True,
            completion=await complete_bootstrap(session, setup, account, device, settings),
        )
    await session.commit()
    return response


@router.post("/mfa/confirm", response_model=BootstrapCompletion)
async def confirm_bootstrap_mfa(
    payload: BootstrapMfaConfirm,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> BootstrapCompletion:
    """Enable first MFA, then approve the already-proven device and ordinary session."""

    setup, account, device = await bootstrap_principal(
        session, _setup_token(authorization), settings
    )
    recovery_codes = await enable_bootstrap_mfa(
        session, setup, account, payload.code, settings
    )
    response = await complete_bootstrap(
        session, setup, account, device, settings, recovery_codes
    )
    await session.commit()
    return response


def _setup_token(authorization: str | None) -> str:
    """Parse a standard bearer header that is resolved only in the bootstrap table."""

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bootstrap session is unavailable")
    return authorization[7:]


async def _rate_limit(
    action: str, client_ip: str, subject: str, settings: Settings
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
