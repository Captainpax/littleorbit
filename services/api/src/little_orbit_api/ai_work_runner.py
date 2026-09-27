"""Run one shared-GPU task under host ownership and a fenced database lease."""

import asyncio
import logging
from contextlib import suppress
from datetime import date, datetime, timedelta
from time import monotonic
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx
from little_orbit_ai.ollama import OllamaClient, OllamaSettings

from .admin_operations import process_quiz_admin_job
from .ai_work_queue import (
    ADMIN_GENERATION,
    ADMIN_LEARNING,
    ADMIN_REGENERATION,
    WEEKLY_GENERATION,
    WEEKLY_LEARNING,
    AiWorkLease,
    claim_due_work,
    complete_work,
    defer_due_work,
    enqueue_due_weekly_work,
    enqueue_pending_admin_work,
    heartbeat_work,
    lease_is_current,
    retry_work,
)
from .clock import SystemClock
from .config import Settings
from .gpu_coordination import try_acquire_gpu_lock
from .quiz_learning_service import (
    RUN_TAKEOVER_AFTER,
    ai_run_is_finished,
    claim_ai_run,
    finish_ai_run,
    learn_feedback_week,
)

LOGGER = logging.getLogger(__name__)


class GenerateWeek(Protocol):
    async def __call__(
        self,
        week_start: date,
        *,
        force: bool = False,
        lease: AiWorkLease | None = None,
    ) -> dict[str, int]: ...


class PrepareWeek(Protocol):
    async def __call__(
        self,
        week_start: date,
        settings: Settings,
        *,
        lease: AiWorkLease | None = None,
    ) -> None: ...


async def run_ai_work_cycle(
    now: datetime,
    settings: Settings,
    model_settings: OllamaSettings,
    generate_week: GenerateWeek,
    prepare_week: PrepareWeek,
) -> str:
    """Queue due work, then run at most one item inside the six-hour cadence."""

    stale_after = timedelta(minutes=settings.ai_lease_stale_minutes)
    retry_after = timedelta(hours=settings.ai_work_retry_hours)
    await enqueue_due_weekly_work(now, settings)
    await enqueue_pending_admin_work(now, stale_after)
    lock = try_acquire_gpu_lock(settings.gpu_lock_path)
    if lock is None:
        await defer_due_work(now, retry_after)
        return "gpu_busy"
    with lock:
        if settings.gpu_verify_idle_processes and not await _prepare_idle_gpu(
            model_settings, settings.gpu_release_timeout_seconds
        ):
            await defer_due_work(now, retry_after)
            return "gpu_process_busy"
        lease = await claim_due_work(
            now,
            stale_after=stale_after,
            minimum_gap=retry_after,
        )
        if lease is None:
            return "idle"
        return await _run_lease(
            lease,
            settings,
            model_settings,
            generate_week,
            prepare_week,
            retry_after,
        )


async def _run_lease(
    lease: AiWorkLease,
    settings: Settings,
    model_settings: OllamaSettings,
    generate_week: GenerateWeek,
    prepare_week: PrepareWeek,
    retry_after: timedelta,
) -> str:
    heartbeat = asyncio.create_task(_heartbeat_forever(lease, settings))
    execution = asyncio.create_task(
        _execute_work(
            lease, settings, model_settings, generate_week, prepare_week
        )
    )
    cleanup_attempted = False
    try:
        completed, _pending = await asyncio.wait(
            {execution, heartbeat},
            timeout=_runtime_limit_seconds(settings),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not completed:
            raise TimeoutError("AI work exceeded its bounded GPU runtime")
        if heartbeat in completed:
            await heartbeat
            raise RuntimeError("AI work heartbeat stopped before execution completed")
        await execution
        cleanup_attempted = True
        await _wait_for_ollama_idle(model_settings, settings.gpu_release_timeout_seconds)
        if heartbeat.done():
            await heartbeat
        if not await complete_work(lease, SystemClock().now()):
            raise RuntimeError("AI work lease expired before completion")
        return "passed"
    except Exception:
        execution.cancel()
        await asyncio.gather(execution, return_exceptions=True)
        if not cleanup_attempted:
            with suppress(Exception):
                await _wait_for_ollama_idle(
                    model_settings, settings.gpu_release_timeout_seconds
                )
        await retry_work(lease, SystemClock().now(), retry_after)
        raise
    finally:
        heartbeat.cancel()
        execution.cancel()
        await asyncio.gather(heartbeat, execution, return_exceptions=True)


def _runtime_limit_seconds(settings: Settings) -> int:
    """Leave enough stale-window time for heartbeat jitter and model unload."""

    stale_seconds = min(
        settings.ai_lease_stale_minutes * 60,
        int(RUN_TAKEOVER_AFTER.total_seconds()),
    )
    cleanup_margin = max(
        settings.ai_lease_heartbeat_seconds * 2,
        settings.gpu_release_timeout_seconds + 60,
    )
    return min(settings.ai_work_max_runtime_seconds, stale_seconds - cleanup_margin)


async def _execute_work(
    lease: AiWorkLease,
    settings: Settings,
    model_settings: OllamaSettings,
    generate_week: GenerateWeek,
    prepare_week: PrepareWeek,
) -> None:
    if not await lease_is_current(lease):
        raise RuntimeError("AI work lease expired before execution")
    local_date = lease.scheduled_at.astimezone(
        ZoneInfo(settings.ai_schedule_timezone)
    ).date()
    if lease.kind == WEEKLY_LEARNING:
        await learn_feedback_week(
            local_date - timedelta(days=5),
            OllamaClient(model_settings),
            lease=lease,
        )
        await prepare_week(local_date + timedelta(days=2), settings, lease=lease)
        await prepare_week(local_date + timedelta(days=9), settings, lease=lease)
        return
    if lease.kind == WEEKLY_GENERATION:
        await _run_generation_horizon(
            lease, local_date + timedelta(days=1), generate_week
        )
        return
    if lease.kind in {ADMIN_LEARNING, ADMIN_GENERATION, ADMIN_REGENERATION}:
        await process_quiz_admin_job(
            lease,
            OllamaClient(model_settings),
            generate_week,
        )
        return
    raise RuntimeError("AI work queue contained an unknown kind")


async def _run_generation_horizon(
    lease: AiWorkLease, week_start: date, generate_week: GenerateWeek
) -> None:
    run_key = f"generate:{week_start.isoformat()}"
    now = SystemClock().now()
    if not await claim_ai_run(run_key, "generation", now, lease=lease):
        if await ai_run_is_finished(run_key):
            return
        raise RuntimeError("AI generation run is already active")
    try:
        first = await generate_week(week_start, lease=lease)
        second = await generate_week(week_start + timedelta(days=7), lease=lease)
        summary = _merge_generation_summaries(first, second)
        status = (
            "passed"
            if summary["fallback_days"] == 0
            and summary["context_stale_sources"] == 0
            else "fallback"
        )
        if not await lease_is_current(lease):
            raise RuntimeError("AI work lease expired during generation")
        await finish_ai_run(run_key, status, summary, lease=lease)
    except Exception:
        await finish_ai_run(
            run_key, "failed", {"reason": "internal_failure"}, lease=lease
        )
        raise


def _merge_generation_summaries(
    first: dict[str, int], second: dict[str, int]
) -> dict[str, object]:
    return {
        "generated_days": first.get("generated_days", 0)
        + second.get("generated_days", 0),
        "fallback_days": first.get("fallback_days", 0)
        + second.get("fallback_days", 0),
        "existing_days": first.get("existing_days", 0)
        + second.get("existing_days", 0),
        "context_stale_sources": max(
            first.get("context_stale_sources", 0),
            second.get("context_stale_sources", 0),
        ),
    }


async def _heartbeat_forever(lease: AiWorkLease, settings: Settings) -> None:
    while True:
        await asyncio.sleep(settings.ai_lease_heartbeat_seconds)
        if not await heartbeat_work(lease, SystemClock().now()):
            raise RuntimeError("AI work lease was replaced while running")


async def _wait_for_ollama_idle(
    settings: OllamaSettings, timeout_seconds: int
) -> None:
    """Request immediate unload and retain the host lock until ``/api/ps`` is empty."""

    deadline = monotonic() + timeout_seconds
    async with httpx.AsyncClient(
        base_url=settings.base_url,
        timeout=httpx.Timeout(5.0),
    ) as client:
        while monotonic() < deadline:
            try:
                response = await client.get("/api/ps")
                response.raise_for_status()
                models = response.json().get("models", [])
            except (httpx.HTTPError, TypeError, ValueError):
                await asyncio.sleep(1)
                continue
            if not models:
                return
            await _request_model_unloads(client, models)
            await asyncio.sleep(1)
    raise RuntimeError("Ollama kept a model loaded beyond the GPU release deadline")


async def _prepare_idle_gpu(
    settings: OllamaSettings, timeout_seconds: int
) -> bool:
    """Unload stale Ollama state and reject compute, graphics, or encoder owners."""

    try:
        await _wait_for_ollama_idle(settings, timeout_seconds)
        compute = await _nvidia_smi_output(
            "--query-compute-apps=pid", "--format=csv,noheader,nounits"
        )
        process_monitor = await _nvidia_smi_output("pmon", "-c", "1")
    except (FileNotFoundError, OSError, RuntimeError, TimeoutError):
        return False
    return not compute.strip() and not _pmon_has_active_pid(process_monitor)


async def _nvidia_smi_output(*arguments: str) -> bytes:
    process = await asyncio.create_subprocess_exec(
        "nvidia-smi",
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=10)
    except BaseException:
        with suppress(ProcessLookupError):
            process.kill()
        await process.wait()
        raise
    if process.returncode != 0:
        raise RuntimeError("NVIDIA process ownership could not be verified")
    return output


def _pmon_has_active_pid(output: bytes) -> bool:
    """Treat every numeric PID row as active, including encoder-only work."""

    for raw_line in output.decode("utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        columns = line.split()
        if len(columns) >= 2 and columns[1].isdigit() and int(columns[1]) > 0:
            return True
    return False


async def _request_model_unloads(
    client: httpx.AsyncClient, models: object
) -> None:
    if not isinstance(models, list):
        raise RuntimeError("Ollama process response has an invalid model list")
    for item in models:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise RuntimeError("Ollama process response has invalid model metadata")
        with suppress(httpx.HTTPError):
            await client.post(
                "/api/generate",
                json={"model": item["name"], "keep_alive": 0},
            )
