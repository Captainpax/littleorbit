"""Maintenance worker for privacy expiry and scheduled application jobs."""

import asyncio
import logging
import os
from datetime import date, timedelta

from little_orbit_ai.ollama import OllamaClient, OllamaSettings
from little_orbit_ai.pipeline import PipelineResult, generate_pool, load_curated_bank
from little_orbit_ai.safety import normalized_hash
from little_orbit_ai.schemas import CandidateQuestion, Category, QuestionKind
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .config import get_settings
from .database import SessionFactory
from .mail import deliver_pending_mail
from .models import (
    Account,
    CuratedBankQuestion,
    DeletionJob,
    GenerationBatch,
    LocationSample,
    MailOutbox,
    OneUseToken,
    Question,
    Session,
)

LOGGER = logging.getLogger(__name__)


async def run_maintenance_once() -> None:
    """Delete expired raw coordinates and expired authentication material."""

    now = SystemClock().now()
    async with SessionFactory() as session:
        await session.execute(delete(LocationSample).where(LocationSample.expires_at <= now))
        await session.execute(
            delete(OneUseToken).where(
                OneUseToken.expires_at <= now - timedelta(days=7),
            )
        )
        await session.execute(delete(Session).where(Session.expires_at <= now - timedelta(days=7)))
        jobs = list(
            await session.scalars(
                select(DeletionJob)
                .where(
                    DeletionJob.status == "scheduled",
                    DeletionJob.execute_after <= now,
                    DeletionJob.account_id.is_not(None),
                )
                .with_for_update(skip_locked=True)
            )
        )
        for job in jobs:
            account = await session.get(Account, job.account_id)
            job.status = "completed"
            job.completed_at = now
            job.account_id = None
            if account is not None:
                await session.execute(
                    delete(MailOutbox).where(MailOutbox.recipient == account.email_normalized)
                )
                await session.delete(account)
        await session.commit()


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
                    Question.publish_date >= target - timedelta(days=6),
                    Question.publish_date < target,
                )
                .order_by(Question.publish_date.desc())
            )
        )


async def _pool_exists(target: date) -> bool:
    async with SessionFactory() as session:
        question_id = await session.scalar(
            select(Question.id)
            .where(Question.publish_date == target, Question.couple_id.is_(None))
            .limit(1)
        )
    return question_id is not None


async def _curated_bank() -> list[CandidateQuestion] | None:
    async with SessionFactory() as session:
        records = list(
            await session.scalars(
                select(CuratedBankQuestion)
                .where(CuratedBankQuestion.enabled.is_(True))
                .order_by(CuratedBankQuestion.stable_key)
            )
        )
    bank = [
        CandidateQuestion(
            client_id=item.stable_key,
            kind=QuestionKind(item.kind),
            prompt=item.prompt,
            category=Category(item.category),
            intimacy=item.intimacy,
            options=item.options,
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
) -> None:
    async with SessionFactory() as session:
        candidates, database_quarantine = await _database_filtered_pool(
            session, target, result, bank
        )
        bank_ids = {item.client_id for item in bank}
        stored = [
            Question(
                publish_date=target,
                kind=item.kind.value,
                prompt=item.prompt,
                category=item.category.value,
                intimacy=item.intimacy,
                options=item.options,
                source="curated" if item.client_id in bank_ids else "ollama",
                normalized_hash=normalized_hash(item.prompt),
            )
            for item in candidates
        ]
        session.add_all(stored)
        await session.flush()
        session.add(
            _generation_record(
                target, result, settings, stored, database_quarantine
            )
        )
        await session.commit()


async def _is_database_duplicate(
    session: AsyncSession, target: date, item: CandidateQuestion
) -> bool:
    digest = normalized_hash(item.prompt)
    matches = await session.scalar(
        select(func.count()).select_from(Question).where(
            Question.couple_id.is_(None),
            Question.publish_date >= target - timedelta(days=6),
            Question.publish_date < target,
            or_(
                Question.normalized_hash == digest,
                func.similarity(Question.prompt, item.prompt) >= 0.72,
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
        selected_question_ids=[str(item.id) for item in stored],
        fallback_reason=fallback_reason,
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
    for offset in range(days):
        target = date.today() + timedelta(days=offset)
        if await _pool_exists(target):
            continue
        recent = await _recent_question_prompts(target)
        result = await generate_pool(target, recent, client, settings, curated_bank)
        await _persist_pool(target, result, settings, effective_bank)


async def run_forever(interval_seconds: int = 300) -> None:
    """Run bounded maintenance repeatedly while allowing container shutdown."""

    while True:
        try:
            await run_maintenance_once()
            await deliver_pending_mail(get_settings())
            await ensure_question_coverage()
        except Exception:
            LOGGER.exception("maintenance cycle failed")
        await asyncio.sleep(max(interval_seconds, 3600))


def main() -> None:
    """Start the worker process."""

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
