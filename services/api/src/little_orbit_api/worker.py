"""Maintenance worker for privacy expiry and scheduled application jobs."""

import asyncio
import logging
import os
from datetime import UTC, date, datetime, time, timedelta
from time import perf_counter

from little_orbit_ai.embeddings import OllamaEmbeddingClient
from little_orbit_ai.ollama import OllamaClient, OllamaSettings
from little_orbit_ai.pipeline import generate_pool, load_curated_bank, select_pool
from little_orbit_ai.schemas import CandidateQuestion, LearningPolicy

from .admin_operations import process_quiz_admin_jobs, refresh_admin_alerts
from .clock import SystemClock
from .config import get_settings
from .mail import deliver_pending_mail
from .maintenance import run_maintenance_once
from .public_context import load_public_context
from .quiz_generation_pool_service import (
    curated_bank,
    embedding_settings,
    is_coverage_seed,
    persist_pool,
    pool_exists,
    recent_question_prompts,
    record_seed_attempt,
    replace_unanswered_pool,
)
from .quiz_learning_service import (
    active_learning_policy,
    claim_ai_run,
    finish_ai_run,
    learn_feedback_week,
)
from .quiz_notification_scheduler import ensure_daily_quiz_notifications

LOGGER = logging.getLogger(__name__)


def _ollama_settings() -> OllamaSettings:
    return OllamaSettings(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        model=os.getenv("OLLAMA_MODEL", "qwen3:4b-instruct-2507-q4_K_M"),
        manifest_digest=os.getenv("OLLAMA_MODEL_DIGEST", OllamaSettings().manifest_digest),
    )


async def ensure_question_coverage(days: int = 7) -> None:
    """Seed missing dates from the safe bank so model outages never create gaps.

    Serving uses each client's validated local date. Maintaining future UTC dates
    plus the current date provides a safe baseline. The Sunday job replaces these
    seeds with validated model output for the next Monday-through-Sunday week.
    """

    settings = _ollama_settings()
    embedding_client = OllamaEmbeddingClient(embedding_settings())
    database_bank = await curated_bank()
    effective_bank = database_bank or load_curated_bank()
    today = SystemClock().now().date()
    targets = [today + timedelta(days=offset) for offset in range(days + 1)]
    for target in targets:
        if not await pool_exists(target):
            if not await replace_unanswered_pool(target):
                continue
            recent = await recent_question_prompts(target)
            seed = select_pool(target, None, recent, settings, "coverage_seed", database_bank)
            await persist_pool(target, seed, settings, effective_bank, 0, embedding_client)


async def generate_question_week(week_start: date) -> dict[str, int]:
    """Generate the exact next Monday-to-Sunday set using the active policy."""

    settings = _ollama_settings()
    client = OllamaClient(settings)
    embedding_client = OllamaEmbeddingClient(embedding_settings())
    database_bank = await curated_bank()
    effective_bank = database_bank or load_curated_bank()
    policy = await active_learning_policy()
    public_context = await load_public_context()
    generated = 0
    fallback = 0
    for offset in range(7):
        target = week_start + timedelta(days=offset)
        if not await pool_exists(target):
            recent = await recent_question_prompts(target)
            seed = select_pool(target, None, recent, settings, "coverage_seed", database_bank)
            await persist_pool(
                target,
                seed,
                settings,
                effective_bank,
                0,
                embedding_client,
            )
        try:
            improved = await _improve_seeded_pool(
                target,
                client,
                settings,
                effective_bank,
                database_bank,
                embedding_client,
                policy,
                public_context,
            )
            generated += int(improved)
            fallback += int(not improved)
        except Exception:
            fallback += 1
            LOGGER.exception("Weekly generation failed for %s; safe seed remains", target)
    return {"generated_days": generated, "fallback_days": fallback}


async def _improve_seeded_pool(
    target: date,
    client: OllamaClient,
    settings: OllamaSettings,
    bank: list[CandidateQuestion],
    database_bank: list[CandidateQuestion] | None,
    embedding_client: OllamaEmbeddingClient,
    policy: LearningPolicy | None = None,
    public_context: list[str] | None = None,
) -> bool:
    if not await is_coverage_seed(target):
        return False
    recent = await recent_question_prompts(target)
    started = perf_counter()
    result = await generate_pool(
        target,
        recent,
        client,
        settings,
        database_bank,
        policy,
        public_context,
    )
    duration_ms = int((perf_counter() - started) * 1000)
    bank_ids = {item.client_id for item in bank}
    selected = [*result.pool.general, *result.pool.intimacy_alternatives]
    if all(item.client_id in bank_ids for item in selected):
        await record_seed_attempt(target, result, duration_ms)
        return False
    if await replace_unanswered_pool(target):
        await persist_pool(
            target,
            result,
            settings,
            bank,
            duration_ms,
            embedding_client,
        )
        return True
    return False


async def run_weekly_quiz_jobs(now: datetime | None = None) -> None:
    """Catch up the latest due Saturday learning and Sunday generation runs."""

    current = now or SystemClock().now()
    settings = get_settings()
    learning_date = _latest_due_date(current, 5, settings.ai_learning_hour_utc)
    if learning_date is not None:
        await learn_feedback_week(
            learning_date - timedelta(days=5),
            OllamaClient(_ollama_settings()),
        )
    generation_date = _latest_due_date(current, 6, settings.ai_generation_hour_utc)
    if generation_date is None:
        return
    week_start = generation_date + timedelta(days=1)
    run_key = f"generate:{week_start.isoformat()}"
    if not await claim_ai_run(run_key, "generation", current):
        return
    try:
        generated_summary = await generate_question_week(week_start)
        summary: dict[str, object] = dict(generated_summary)
        status = "passed" if summary["fallback_days"] == 0 else "fallback"
        await finish_ai_run(run_key, status, summary)
    except Exception:
        await finish_ai_run(run_key, "failed", {"reason": "internal_failure"})
        raise


def _latest_due_date(current: datetime, weekday: int, hour: int) -> date | None:
    """Return the latest UTC schedule date at or before the current instant."""

    aware = current.astimezone(UTC)
    candidate = aware.date() - timedelta(days=(aware.weekday() - weekday) % 7)
    scheduled = datetime.combine(candidate, time(hour=hour), tzinfo=UTC)
    if scheduled > aware:
        candidate -= timedelta(days=7)
    return candidate


async def _poll_mail_forever(interval_seconds: int) -> None:
    while True:
        try:
            await deliver_pending_mail(get_settings())
        except Exception:
            LOGGER.exception("mail delivery cycle failed")
        await asyncio.sleep(max(interval_seconds, 5))


async def _run_scheduled_jobs_forever(interval_seconds: int) -> None:
    while True:
        try:
            await ensure_question_coverage()
        except Exception:
            LOGGER.exception("question coverage cycle failed")
        try:
            await run_weekly_quiz_jobs()
        except Exception:
            LOGGER.exception("weekly quiz intelligence cycle failed")
        try:
            await process_quiz_admin_jobs(
                OllamaClient(_ollama_settings()),
                generate_question_week,
            )
            await refresh_admin_alerts()
        except Exception:
            LOGGER.exception("Big Orbit operations cycle failed")
        try:
            await ensure_daily_quiz_notifications()
        except Exception:
            LOGGER.exception("daily quiz notification cycle failed")
        await asyncio.sleep(max(interval_seconds, 3600))


async def _run_privacy_maintenance_forever(interval_seconds: int) -> None:
    """Enforce short-lived location and deletion policies at least every five minutes."""

    while True:
        try:
            await run_maintenance_once()
        except Exception:
            LOGGER.exception("privacy maintenance cycle failed")
        await asyncio.sleep(max(interval_seconds, 300))


async def run_forever(
    mail_interval_seconds: int = 30,
    privacy_interval_seconds: int = 300,
    scheduled_interval_seconds: int = 3600,
) -> None:
    """Run mail polling independently from slower maintenance and AI work."""

    await asyncio.gather(
        _poll_mail_forever(mail_interval_seconds),
        _run_privacy_maintenance_forever(privacy_interval_seconds),
        _run_scheduled_jobs_forever(scheduled_interval_seconds),
    )


def main() -> None:
    """Start the worker process."""

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
