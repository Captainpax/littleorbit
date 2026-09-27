"""Maintenance worker for privacy expiry and scheduled application jobs."""

import asyncio
import logging
import os
from datetime import date, datetime, timedelta
from time import perf_counter

from little_orbit_ai.embeddings import OllamaEmbeddingClient
from little_orbit_ai.ollama import OllamaClient, OllamaSettings
from little_orbit_ai.pipeline import generate_pool, load_curated_bank, select_pool
from little_orbit_ai.schemas import CandidateQuestion, DayTheme, LearningPolicy

from .admin_operations import refresh_admin_alerts
from .ai_work_queue import AiWorkLease, AiWorkLeaseExpired, latest_due_date
from .ai_work_runner import run_ai_work_cycle
from .clock import SystemClock
from .config import Settings, get_settings
from .mail import deliver_pending_mail
from .maintenance import run_maintenance_once
from .public_context import PublicContextBundle, load_public_context_bundle
from .quiz_generation_pool_service import (
    curated_bank,
    embedding_settings,
    is_coverage_seed,
    persist_pool,
    pool_exists,
    recent_question_prompts,
    record_seed_attempt,
)
from .quiz_knowledge_service import retrieve_knowledge, sync_reviewed_knowledge
from .quiz_learning_service import active_learning_policy
from .quiz_notification_scheduler import ensure_daily_quiz_notifications
from .quiz_reserve_service import sync_question_reserve
from .quiz_theme_service import (
    mark_week_published,
    plan_quiz_week,
    quiz_week_planned,
    theme_for_date,
)

LOGGER = logging.getLogger(__name__)


def _ollama_settings() -> OllamaSettings:
    return OllamaSettings(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        model=os.getenv("OLLAMA_MODEL", "qwen3:4b-instruct-2507-q4_K_M"),
        manifest_digest=os.getenv("OLLAMA_MODEL_DIGEST", OllamaSettings().manifest_digest),
    )


def _latest_due_date(
    current: datetime, weekday: int, hour: int, timezone: str = "UTC"
) -> date:
    """Compatibility wrapper around the local-time queue scheduler."""

    return latest_due_date(current, weekday, hour, timezone)


async def ensure_question_coverage(days: int | None = None) -> None:
    """Seed missing dates from the safe bank so model outages never create gaps.

    Serving uses each client's validated local date. Fourteen consecutive UTC-date
    slots provide a safe baseline without contacting Ollama. Weekend GPU work then
    replaces eligible seeds with validated model output for two full quiz weeks.
    """

    await sync_question_reserve()
    runtime = get_settings()
    settings = _ollama_settings()
    embedding_client = OllamaEmbeddingClient(embedding_settings())
    database_bank = await curated_bank()
    effective_bank = database_bank or load_curated_bank()
    today = SystemClock().now().date()
    coverage_days = days if days is not None else runtime.ai_coverage_days
    targets = [today + timedelta(days=offset) for offset in range(coverage_days)]
    for target in targets:
        if not await pool_exists(target):
            recent = await recent_question_prompts(target)
            theme = await theme_for_date(target)
            seed = select_pool(
                target,
                None,
                recent,
                settings,
                "coverage_seed",
                database_bank,
                theme.day if theme else None,
            )
            await persist_pool(
                target,
                seed,
                settings,
                effective_bank,
                0,
                embedding_client,
                allow_embeddings=False,
            )


async def generate_question_week(
    week_start: date,
    *,
    force: bool = False,
    lease: AiWorkLease | None = None,
) -> dict[str, int]:
    """Generate the exact next Monday-to-Sunday set using the active policy."""

    settings = _ollama_settings()
    client = OllamaClient(settings)
    embedding_client = OllamaEmbeddingClient(embedding_settings())
    database_bank = await curated_bank()
    effective_bank = database_bank or load_curated_bank()
    policy = await active_learning_policy()
    context = await load_public_context_bundle(lease=lease)
    await _prepare_week_intelligence(
        week_start, client, embedding_client, policy, context, lease=lease
    )
    generated = 0
    fallback = 0
    existing = 0
    for offset in range(7):
        target = week_start + timedelta(days=offset)
        if not force and await pool_exists(target) and not await is_coverage_seed(target):
            existing += 1
            continue
        try:
            improved = await _generate_question_day(
                target,
                force,
                client,
                settings,
                database_bank,
                effective_bank,
                embedding_client,
                policy,
                context,
                lease,
            )
            generated += int(improved)
            fallback += int(not improved)
        except AiWorkLeaseExpired:
            raise
        except Exception:
            fallback += 1
            LOGGER.exception("Weekly generation failed for %s; safe seed remains", target)
    if generated + fallback + existing == 7:
        await mark_week_published(week_start, lease=lease)
    return {
        "generated_days": generated,
        "fallback_days": fallback,
        "existing_days": existing,
        "context_stale_sources": len(context.stale_sources),
    }


async def _generate_question_day(
    target: date,
    force: bool,
    client: OllamaClient,
    settings: OllamaSettings,
    database_bank: list[CandidateQuestion] | None,
    effective_bank: list[CandidateQuestion],
    embedding_client: OllamaEmbeddingClient,
    policy: LearningPolicy | None,
    context: PublicContextBundle,
    lease: AiWorkLease | None = None,
) -> bool:
    """Seed one day safely, then replace it only with a validated generated pool."""

    theme = await theme_for_date(target)
    day_theme = theme.day if theme else None
    knowledge = await retrieve_knowledge(
        _knowledge_query(day_theme.title if day_theme else "evergreen couples questions"),
        embedding_client,
    )
    if not await pool_exists(target):
        seed = select_pool(
            target,
            None,
            await recent_question_prompts(target),
            settings,
            "coverage_seed",
            database_bank,
            day_theme,
            knowledge.revision,
            context.digest,
        )
        await persist_pool(
            target,
            seed,
            settings,
            effective_bank,
            0,
            embedding_client,
            lease=lease,
        )
    return await _improve_seeded_pool(
        target,
        force,
        client,
        settings,
        effective_bank,
        database_bank,
        embedding_client,
        policy,
        context,
        day_theme,
        knowledge.snippets,
        knowledge.revision,
        lease,
    )


async def _improve_seeded_pool(
    target: date,
    force: bool,
    client: OllamaClient,
    settings: OllamaSettings,
    bank: list[CandidateQuestion],
    database_bank: list[CandidateQuestion] | None,
    embedding_client: OllamaEmbeddingClient,
    policy: LearningPolicy | None = None,
    public_context: PublicContextBundle | None = None,
    day_theme: DayTheme | None = None,
    knowledge: list[str] | None = None,
    knowledge_revision: str | None = None,
    lease: AiWorkLease | None = None,
) -> bool:
    if not force and not await is_coverage_seed(target):
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
        public_context.snippets if public_context else None,
        day_theme,
        knowledge,
        knowledge_revision,
        public_context.digest if public_context else None,
    )
    duration_ms = int((perf_counter() - started) * 1000)
    bank_ids = {item.client_id for item in bank}
    selected = [*result.pool.general, *result.pool.intimacy_alternatives]
    if all(item.client_id in bank_ids for item in selected):
        await record_seed_attempt(target, result, duration_ms, lease=lease)
        return False
    return await persist_pool(
        target,
        result,
        settings,
        bank,
        duration_ms,
        embedding_client,
        lease=lease,
    )


async def run_weekly_quiz_jobs(now: datetime | None = None) -> None:
    """Queue due work and run at most one lease-fenced shared-GPU operation."""

    current = now or SystemClock().now()
    settings = get_settings()
    await run_ai_work_cycle(
        current,
        settings,
        _ollama_settings(),
        generate_question_week,
        _prepare_saturday_plan,
    )


async def _prepare_saturday_plan(
    week_start: date,
    settings: Settings,
    *,
    lease: AiWorkLease | None = None,
) -> None:
    if await quiz_week_planned(week_start):
        return
    model = OllamaClient(_ollama_settings())
    embeddings = OllamaEmbeddingClient(embedding_settings())
    context = await load_public_context_bundle(settings, lease=lease)
    policy = await active_learning_policy()
    await _prepare_week_intelligence(
        week_start, model, embeddings, policy, context, settings, lease
    )


async def _prepare_week_intelligence(
    week_start: date,
    model: OllamaClient,
    embeddings: OllamaEmbeddingClient,
    policy: LearningPolicy | None,
    context: PublicContextBundle,
    runtime: Settings | None = None,
    lease: AiWorkLease | None = None,
) -> None:
    settings = runtime or get_settings()
    try:
        await sync_reviewed_knowledge(embeddings, lease=lease)
    except AiWorkLeaseExpired:
        raise
    except Exception:
        LOGGER.exception("Reviewed knowledge sync failed; prior revision remains active")
    knowledge = await retrieve_knowledge("weekly theme planning", embeddings)
    await plan_quiz_week(
        week_start,
        model,
        policy,
        context.snippets,
        knowledge.snippets,
        timezone=settings.ai_schedule_timezone,
        locale=settings.ai_theme_locale,
        lease=lease,
    )


def _knowledge_query(theme_title: str) -> str:
    return f"couples quiz theme {theme_title} emotional depth safety variety"


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
            await refresh_admin_alerts()
        except Exception:
            LOGGER.exception("Big Orbit alert refresh failed")
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
