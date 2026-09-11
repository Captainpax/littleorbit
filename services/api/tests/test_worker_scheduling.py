"""Worker cadence and job-isolation behavior."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from little_orbit_api import worker


async def test_mail_polling_uses_short_bounded_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    delivery = AsyncMock()
    observed_delays: list[int] = []

    async def stop_after_first_cycle(delay: int) -> None:
        observed_delays.append(delay)
        raise asyncio.CancelledError

    monkeypatch.setattr(worker, "deliver_pending_mail", delivery)
    monkeypatch.setattr(worker, "get_settings", lambda: object())
    monkeypatch.setattr(worker.asyncio, "sleep", stop_after_first_cycle)

    with pytest.raises(asyncio.CancelledError):
        await worker._poll_mail_forever(interval_seconds=0)

    delivery.assert_awaited_once()
    assert observed_delays == [5]


async def test_scheduled_jobs_keep_hourly_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    maintenance = AsyncMock()
    question_coverage = AsyncMock()
    observed_delays: list[int] = []

    async def stop_after_first_cycle(delay: int) -> None:
        observed_delays.append(delay)
        raise asyncio.CancelledError

    monkeypatch.setattr(worker, "run_maintenance_once", maintenance)
    monkeypatch.setattr(worker, "ensure_question_coverage", question_coverage)
    monkeypatch.setattr(worker.asyncio, "sleep", stop_after_first_cycle)

    with pytest.raises(asyncio.CancelledError):
        await worker._run_scheduled_jobs_forever(interval_seconds=0)

    maintenance.assert_awaited_once()
    question_coverage.assert_awaited_once()
    assert observed_delays == [3600]
