"""Liveness, readiness, and public service status routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..database import session_scope
from ..schemas import HealthResponse

router = APIRouter(prefix="/v1/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    """Return process liveness without touching a dependency."""

    return HealthResponse(
        status="ok", service="api", version="1.3.0", checked_at=SystemClock().now()
    )


@router.get("/ready", response_model=HealthResponse)
async def ready(session: AsyncSession = Depends(session_scope)) -> HealthResponse:
    """Return readiness after a minimal database round trip."""

    await session.execute(text("SELECT 1"))
    return HealthResponse(
        status="ok", service="api", version="1.3.0", checked_at=SystemClock().now()
    )
