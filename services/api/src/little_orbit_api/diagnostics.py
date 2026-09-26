"""Content-free grouping and retention for opt-in Android crash diagnostics."""

import hashlib
import json
from datetime import datetime, timedelta

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from .diagnostic_models import CrashReport
from .diagnostic_schemas import CrashFrame


def canonical_diagnostic(
    exception_chain: list[str], frames: list[CrashFrame]
) -> tuple[str, str]:
    """Encode only validated class and method identifiers for bounded retention."""

    chain_json = json.dumps(exception_chain, separators=(",", ":"))
    frame_json = json.dumps(
        [frame.model_dump(mode="json") for frame in frames], separators=(",", ":")
    )
    return chain_json, frame_json


def diagnostic_fingerprint(exception_chain: list[str], frames: list[CrashFrame]) -> str:
    """Create a content-free grouping key from validated code identifiers."""

    chain_json, frame_json = canonical_diagnostic(exception_chain, frames)
    return hashlib.sha256(f"{chain_json}\n{frame_json}".encode()).hexdigest()


async def purge_diagnostics(session: AsyncSession, now: datetime) -> None:
    """Drop structured detail after 30 days and grouping rows after 90 days."""

    await session.execute(
        update(CrashReport)
        .where(CrashReport.raw_expires_at <= now)
        .values(exception_chain=None, app_frames=None)
    )
    await session.execute(
        delete(CrashReport).where(CrashReport.aggregate_expires_at <= now)
    )


def retention_deadlines(created_at: datetime) -> tuple[datetime, datetime]:
    """Return exact structured-detail and aggregate expiry instants."""

    return created_at + timedelta(days=30), created_at + timedelta(days=90)
