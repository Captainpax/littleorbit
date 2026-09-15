"""Authenticated opt-in crash-report intake with strict privacy limits."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..config import Settings, get_settings
from ..database import session_scope
from ..dependencies import current_account, request_client_ip
from ..diagnostic_models import CrashReport
from ..diagnostic_schemas import CrashReportRequest
from ..diagnostics import canonical_diagnostic, diagnostic_fingerprint, retention_deadlines
from ..models import Account
from ..rate_limit import RateLimitRule, consume_rate_limits, rate_limit_subject
from ..schemas import PublicMessage

router = APIRouter(prefix="/v1/diagnostics", tags=["diagnostics"])


@router.post("/crash", response_model=PublicMessage, status_code=status.HTTP_202_ACCEPTED)
async def report_crash(
    payload: CrashReportRequest,
    _actor: Account = Depends(current_account),
    client_ip: str = Depends(request_client_ip),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(session_scope),
) -> PublicMessage:
    """Accept one consented report without retaining account identity."""

    now = SystemClock().now()
    if payload.occurred_at < now - timedelta(days=7) or payload.occurred_at > now + timedelta(minutes=5):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Diagnostic time is invalid")
    decision = await consume_rate_limits(
        [
            RateLimitRule("diagnostic:ip", client_ip, 50, timedelta(days=1)),
            RateLimitRule(
                "diagnostic:installation",
                str(payload.installation_id),
                10,
                timedelta(days=1),
            ),
        ],
        settings=settings,
    )
    if not decision.allowed:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Diagnostic limit reached")
    exception_chain, app_frames = canonical_diagnostic(
        payload.exception_chain, payload.frames
    )
    raw_expires, aggregate_expires = retention_deadlines(now)
    session.add(
        CrashReport(
            installation_hash=rate_limit_subject(
                "diagnostic-store", str(payload.installation_id), settings
            ),
            app_version_code=payload.app_version_code,
            app_version_name=payload.app_version_name,
            fingerprint=diagnostic_fingerprint(payload.exception_chain, payload.frames),
            exception_chain=exception_chain,
            app_frames=app_frames,
            occurred_at=payload.occurred_at,
            created_at=now,
            raw_expires_at=raw_expires,
            aggregate_expires_at=aggregate_expires,
        )
    )
    await session.commit()
    return PublicMessage(message="Diagnostic accepted.")
