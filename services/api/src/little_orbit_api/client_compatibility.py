"""Android client compatibility gate shared by HTTP and WebSocket entry points."""

from datetime import datetime

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from .clock import SystemClock
from .database import SessionFactory
from .models import ApkRelease
from .schemas import ClientUpdateRequired

CLIENT_HEADER = "x-little-orbit-client"
VERSION_CODE_HEADER = "x-little-orbit-version-code"
MOBILE_PREFIXES = (
    "/v1/account",
    "/v1/countdowns",
    "/v1/couple",
    "/v1/notes",
    "/v1/pairing",
    "/v1/quizzes",
    "/v1/together-time",
)
MOBILE_AUTH_PATHS = {"/v1/auth/login", "/v1/auth/logout", "/v1/auth/session/rotate"}


def is_mobile_http_path(path: str) -> bool:
    """Return whether a route belongs to the installed Android client contract."""

    return path in MOBILE_AUTH_PATHS or path.startswith(MOBILE_PREFIXES)


def supplied_version_code(client: str | None, raw_version_code: str | None) -> int | None:
    """Parse only the explicit Android client identity and positive version code."""

    if client != "android" or raw_version_code is None or not raw_version_code.isdecimal():
        return None
    version_code = int(raw_version_code)
    return version_code if version_code > 0 else None


async def enforced_version_floor(session: AsyncSession, now: datetime) -> int | None:
    """Return the newest active published compatibility floor, if any."""

    return await session.scalar(
        select(ApkRelease.minimum_supported_version_code)
        .where(
            ApkRelease.published_at.is_not(None),
            ApkRelease.required_after.is_not(None),
            ApkRelease.required_after <= now,
            ApkRelease.minimum_supported_version_code.is_not(None),
        )
        .order_by(ApkRelease.version_code.desc())
        .limit(1)
    )


def update_required(version_code: int | None, floor: int | None) -> bool:
    """Fail closed only after an operator has activated a positive floor."""

    return floor is not None and (version_code is None or version_code < floor)


class AndroidCompatibilityMiddleware(BaseHTTPMiddleware):
    """Reject obsolete Android calls before authentication or resource lookup."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not is_mobile_http_path(request.url.path):
            return await call_next(request)
        async with SessionFactory() as session:
            floor = await enforced_version_floor(session, SystemClock().now())
        version_code = supplied_version_code(
            request.headers.get(CLIENT_HEADER), request.headers.get(VERSION_CODE_HEADER)
        )
        if not update_required(version_code, floor):
            return await call_next(request)
        assert floor is not None
        return JSONResponse(
            status_code=426,
            content=ClientUpdateRequired(minimum_version_code=floor).model_dump(),
            headers={"Cache-Control": "no-store"},
        )
