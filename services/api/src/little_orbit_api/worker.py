"""Maintenance worker for privacy expiry and scheduled application jobs."""

import asyncio
import logging
import os
from datetime import date, timedelta
from time import perf_counter

from little_orbit_ai.ollama import OllamaClient, OllamaSettings
from little_orbit_ai.pipeline import (
    PipelineResult,
    generate_pool,
    load_curated_bank,
    select_pool,
)
from little_orbit_ai.safety import normalized_hash
from little_orbit_ai.schemas import CandidateQuestion, Category, IconKey, QuestionKind
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .config import get_settings
from .database import SessionFactory
from .mail import deliver_pending_mail
from .maintenance import run_maintenance_once
from .models import (
    CuratedBankQuestion,
    GenerationBatch,
    Question,
    QuizAnswer,
    QuizDayQuestion,
)
from .push_delivery import deliver_push_wakes_once
from .quiz_notification_scheduler import ensure_daily_quiz_notifications

LOGGER = logging.getLogger(__name__)


def _ollama_settings() -> OllamaSettings:
    return OllamaSettings(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        model=os.getenv("OLLAMA_MODEL", "qwen3:4b-instruct-2507-q4_K_M"),
        manifest_digest=os.getenv("OLLAMA_MODEL_DIGEST", OllamaSettings().manifest_digest),
    )


async def _recent_question_prompts(target: date) -> list[str]:
    async with SessionFactory() as session:
        return list(
            await session.scalars(
                select(Question.prompt)
                .where(
                    Question.couple_id.is_(None),
                    Question.publish_date >= target - timedelta(days=30),
                    Question.publish_date < target,
                )
                .order_by(Question.publish_date.desc())
            )
        )


async def _pool_exists(target: date) -> bool:
    async with SessionFactory() as session:
        general = await session.scalar(
            select(func.count())
            .select_from(Question)
            .where(
                Question.publish_date == target,
                Question.couple_id.is_(None),
                Question.intimacy.is_(False),
                Question.disabled_at.is_(None),
                Question.interaction_version == 2,
            )
        )
        intimacy = await session.scalar(
            select(func.count())
            .select_from(Question)
            .where(
                Question.publish_date == target,
                Question.couple_id.is_(None),
                Question.intimacy.is_(True),
                Question.disabled_at.is_(None),
                Question.interaction_version == 2,
            )
        )
        if target == SystemClock().now().date() and general != 5:
            general = await session.scalar(
                select(func.count())
                .select_from(Question)
                .where(
                    Question.publish_date == target,
                    Question.couple_id.is_(None),
                    Question.intimacy.is_(False),
                    Question.disabled_at.is_(None),
                )
            )
            intimacy = await session.scalar(
                select(func.count())
                .select_from(Question)
                .where(
                    Question.publish_date == target,
                    Question.couple_id.is_(None),
                    Question.intimacy.is_(True),
                    Question.disabled_at.is_(None),
                )
            )
    return general == 5 and bool(intimacy)


async def _curated_bank() -> list[CandidateQuestion] | None:
    async with SessionFactory() as session:
        records = list(
            await session.scalars(
                select(CuratedBankQuestion)
                .where(CuratedBankQuestion.enabled.is_(True))
                .order_by(CuratedBankQuestion.stable_key)
            )
        )
    if any(item.options and not item.option_icons for item in records):
        return None
    bank = [
        CandidateQuestion(
            client_id=item.stable_key,
            kind=QuestionKind(item.kind),
            prompt=item.prompt,
            category=Category(item.category),
            intimacy=item.intimacy,
            options=item.options,
            option_icons=[IconKey(value) for value in item.option_icons],
            scale_low_label=item.scale_low_label,
            scale_high_label=item.scale_high_label,
        )
        for item in records
    ]
    general_count = sum(not item.intimacy for item in bank)
    return bank if general_count >= 5 and any(item.intimacy for item in bank) else None


async def _persist_pool(
    target: date,
    result: PipelineResult,
    settings: OllamaSettings,
    bank: list[CandidateQuestion],
    duration_ms: int,
) -> None:
    async with SessionFactory() as session:
        candidates, database_quarantine = await _database_filtered_pool(
            session, target, result, bank
        )
        bank_ids = {item.client_id for item in bank}
        general_items = [item for item in candidates if not item.intimacy]
        order = {item.client_id: index for index, item in enumerate(general_items, start=1)}
        stored = [
            Question(
                publish_date=target,
                kind=item.kind.value,
                prompt=item.prompt,
                category=item.category.value,
                intimacy=item.intimacy,
                options=item.options,
                option_icons=[icon.value for icon in item.option_icons],
                scale_low_label=item.scale_low_label,
                scale_high_label=item.scale_high_label,
                interaction_version=2,
                display_order=order.get(item.client_id),
                source="curated" if item.client_id in bank_ids else "ollama",
                normalized_hash=normalized_hash(item.prompt),
            )
            for item in candidates
        ]
        session.add_all(stored)
        await session.flush()
        session.add(
            _generation_record(target, result, settings, stored, database_quarantine, duration_ms)
        )
        await session.commit()


async def _is_database_duplicate(
    session: AsyncSession, target: date, item: CandidateQuestion
) -> bool:
    digest = normalized_hash(item.prompt)
    matches = await session.scalar(
        select(func.count())
        .select_from(Question)
        .where(
            Question.couple_id.is_(None),
            Question.publish_date >= target - timedelta(days=30),
            Question.publish_date < target,
            or_(
                Question.normalized_hash == digest,
                func.similarity(Question.prompt, item.prompt) >= 0.82,
            ),
        )
    )
    return bool(matches)


async def _database_filtered_pool(
    session: AsyncSession,
    target: date,
    result: PipelineResult,
    bank: list[CandidateQuestion],
) -> tuple[list[CandidateQuestion], list[dict[str, object]]]:
    selected, rejected = await _filter_database_duplicates(session, target, result)
    general = [item for item in selected if not item.intimacy][:5]
    intimacy = [item for item in selected if item.intimacy]
    await _fill_from_bank(session, target, bank, general, intimacy, selected)
    if len(general) < 5 or not intimacy:
        raise RuntimeError("database duplicate gate exhausted the curated bank")
    return [*general[:5], *intimacy], rejected


async def _filter_database_duplicates(
    session: AsyncSession, target: date, result: PipelineResult
) -> tuple[list[CandidateQuestion], list[dict[str, object]]]:
    selected: list[CandidateQuestion] = []
    rejected: list[dict[str, object]] = []
    proposed = [*result.pool.general, *result.pool.intimacy_alternatives]
    for item in proposed:
        if await _is_database_duplicate(session, target, item):
            rejected.append({"client_id": item.client_id, "reasons": ["database_near_duplicate"]})
        else:
            selected.append(item)
    return selected, rejected


def _needs_bank_item(
    item: CandidateQuestion, general: list[CandidateQuestion], intimacy: list[CandidateQuestion]
) -> bool:
    return (not item.intimacy and len(general) < 5) or (item.intimacy and not intimacy)


async def _fill_from_bank(
    session: AsyncSession,
    target: date,
    bank: list[CandidateQuestion],
    general: list[CandidateQuestion],
    intimacy: list[CandidateQuestion],
    selected: list[CandidateQuestion],
) -> None:
    used = {normalized_hash(item.prompt) for item in selected}
    for item in _rotated_bank(target, bank):
        if not _needs_bank_item(item, general, intimacy):
            continue
        if normalized_hash(item.prompt) in used:
            continue
        if not await _is_database_duplicate(session, target, item):
            (intimacy if item.intimacy else general).append(item)
            used.add(normalized_hash(item.prompt))


def _rotated_bank(target: date, bank: list[CandidateQuestion]) -> list[CandidateQuestion]:
    start = (target.toordinal() * 5) % len(bank)
    return bank[start:] + bank[:start]


def _generation_record(
    target: date,
    result: PipelineResult,
    settings: OllamaSettings,
    stored: list[Question],
    database_quarantine: list[dict[str, object]],
    duration_ms: int,
) -> GenerationBatch:
    fallback_reason = result.pool.fallback_reason
    if database_quarantine and fallback_reason is None:
        fallback_reason = "database_near_duplicate"
    return GenerationBatch(
        publish_date=target,
        model=result.pool.model,
        model_digest=result.pool.model_manifest_digest,
        prompt_version=result.pool.prompt_version,
        parameters={
            "context_tokens": settings.context_tokens,
            "output_tokens": settings.output_tokens,
            "keep_alive": 0,
        },
        validation_results=[
            {"client_id": item.client_id, "reasons": list(item.reasons)}
            for item in result.quarantined
        ]
        + database_quarantine,
        candidate_snapshot=[
            {
                "kind": item.kind.value,
                "prompt": item.prompt,
                "category": item.category.value,
                "intimacy": item.intimacy,
                "options": item.options,
                "option_icons": [icon.value for icon in item.option_icons],
                "scale_low_label": item.scale_low_label,
                "scale_high_label": item.scale_high_label,
            }
            for item in [*result.pool.general, *result.pool.intimacy_alternatives]
        ],
        selected_question_ids=[str(item.id) for item in stored],
        fallback_reason=fallback_reason,
        duration_ms=duration_ms,
        created_at=SystemClock().now(),
    )


async def ensure_question_coverage(days: int = 7) -> None:
    """Generate and persist missing global pools for seven future UTC dates.

    Serving uses each client's validated local date. Maintaining future UTC dates
    plus the current date provides a safe global baseline while timezone-specific
    scheduling is completed.
    """

    settings = _ollama_settings()
    client = OllamaClient(settings)
    curated_bank = await _curated_bank()
    effective_bank = curated_bank or load_curated_bank()
    today = SystemClock().now().date()
    targets = [today + timedelta(days=offset) for offset in range(days + 1)]
    for target in targets:
        if not await _pool_exists(target):
            if not await _replace_unanswered_pool(target):
                continue
            recent = await _recent_question_prompts(target)
            seed = select_pool(target, None, recent, settings, "coverage_seed", curated_bank)
            await _persist_pool(target, seed, settings, effective_bank, 0)
    for target in targets[1:]:
        try:
            await _improve_seeded_pool(target, client, settings, effective_bank, curated_bank)
        except Exception:
            LOGGER.exception("AI improvement failed for %s; curated coverage remains", target)


async def _improve_seeded_pool(
    target: date,
    client: OllamaClient,
    settings: OllamaSettings,
    bank: list[CandidateQuestion],
    database_bank: list[CandidateQuestion] | None,
) -> None:
    async with SessionFactory() as session:
        batch = await session.scalar(
            select(GenerationBatch).where(GenerationBatch.publish_date == target)
        )
        if batch is None or batch.fallback_reason != "coverage_seed":
            return
    recent = await _recent_question_prompts(target)
    started = perf_counter()
    result = await generate_pool(target, recent, client, settings, database_bank)
    duration_ms = int((perf_counter() - started) * 1000)
    bank_ids = {item.client_id for item in bank}
    selected = [*result.pool.general, *result.pool.intimacy_alternatives]
    if all(item.client_id in bank_ids for item in selected):
        await _record_seed_attempt(target, result, duration_ms)
        return
    if await _replace_unanswered_pool(target):
        await _persist_pool(target, result, settings, bank, duration_ms)


async def _record_seed_attempt(target: date, result: PipelineResult, duration_ms: int) -> None:
    """Record a failed AI attempt without disturbing safe curated coverage."""

    async with SessionFactory() as session:
        batch = await session.scalar(
            select(GenerationBatch).where(GenerationBatch.publish_date == target).with_for_update()
        )
        if batch is None or batch.fallback_reason != "coverage_seed":
            return
        batch.duration_ms = duration_ms
        batch.fallback_reason = result.pool.fallback_reason or "no_valid_ai_candidates"
        batch.validation_results = [
            {"client_id": item.client_id, "reasons": list(item.reasons)}
            for item in result.quarantined
        ]
        await session.commit()


async def _replace_unanswered_pool(target: date) -> bool:
    """Remove only a future/global pool that has no answer or day references."""

    async with SessionFactory() as session:
        ids = select(Question.id).where(
            Question.publish_date == target, Question.couple_id.is_(None)
        )
        answered = await session.scalar(
            select(func.count()).select_from(QuizAnswer).where(QuizAnswer.question_id.in_(ids))
        )
        materialized = await session.scalar(
            select(func.count())
            .select_from(QuizDayQuestion)
            .where(QuizDayQuestion.question_id.in_(ids))
        )
        if answered or materialized:
            return False
        await session.execute(delete(GenerationBatch).where(GenerationBatch.publish_date == target))
        await session.execute(
            delete(Question).where(Question.publish_date == target, Question.couple_id.is_(None))
        )
        await session.commit()
    return True


async def _poll_mail_forever(interval_seconds: int) -> None:
    while True:
        try:
            await deliver_pending_mail(get_settings())
        except Exception:
            LOGGER.exception("mail delivery cycle failed")
        await asyncio.sleep(max(interval_seconds, 5))


async def _poll_push_forever(interval_seconds: int) -> None:
    """Dispatch content-free device wakes without coupling them to feature writes."""

    while True:
        try:
            await deliver_push_wakes_once()
        except Exception:
            LOGGER.exception("content-free push cycle failed")
        await asyncio.sleep(max(interval_seconds, 5))


async def _run_scheduled_jobs_forever(interval_seconds: int) -> None:
    while True:
        try:
            await ensure_question_coverage()
        except Exception:
            LOGGER.exception("question coverage cycle failed")
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
    push_interval_seconds: int = 5,
    privacy_interval_seconds: int = 300,
    scheduled_interval_seconds: int = 3600,
) -> None:
    """Run mail polling independently from slower maintenance and AI work."""

    await asyncio.gather(
        _poll_mail_forever(mail_interval_seconds),
        _poll_push_forever(push_interval_seconds),
        _run_privacy_maintenance_forever(privacy_interval_seconds),
        _run_scheduled_jobs_forever(scheduled_interval_seconds),
    )


def main() -> None:
    """Start the worker process."""

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
