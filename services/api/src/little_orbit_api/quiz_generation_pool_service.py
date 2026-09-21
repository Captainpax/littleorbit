"""Persistence and duplicate filtering for scheduled quiz generation."""

import os
from datetime import date, timedelta

from little_orbit_ai.embeddings import EmbeddingSettings, OllamaEmbeddingClient
from little_orbit_ai.ollama import OllamaSettings
from little_orbit_ai.pipeline import PipelineResult
from little_orbit_ai.safety import normalized_hash
from little_orbit_ai.schemas import CandidateQuestion, Category, IconKey, QuestionKind
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .database import SessionFactory
from .models import (
    CuratedBankQuestion,
    GenerationBatch,
    Question,
    QuizAnswer,
    QuizDayQuestion,
)
from .quiz_semantics import (
    CandidateSemantics,
    candidate_semantics,
    concept_record,
    is_semantic_duplicate,
    semantics_overlap,
)


def embedding_settings() -> EmbeddingSettings:
    defaults = EmbeddingSettings()
    return EmbeddingSettings(
        base_url=os.getenv("OLLAMA_BASE_URL", defaults.base_url),
        model=os.getenv("OLLAMA_EMBEDDING_MODEL", defaults.model),
        manifest_digest=os.getenv(
            "OLLAMA_EMBEDDING_MODEL_DIGEST", defaults.manifest_digest
        ),
    )


async def recent_question_prompts(target: date) -> list[str]:
    async with SessionFactory() as session:
        return list(
            await session.scalars(
                select(Question.prompt)
                .where(
                    Question.couple_id.is_(None),
                    Question.publish_date >= target - timedelta(days=365),
                    Question.publish_date < target,
                )
                .order_by(Question.publish_date.desc())
            )
        )


async def pool_exists(target: date) -> bool:
    async with SessionFactory() as session:
        general = await _pool_size(session, target, intimacy=False, v2_only=True)
        intimacy = await _pool_size(session, target, intimacy=True, v2_only=True)
        if target == SystemClock().now().date() and general != 5:
            general = await _pool_size(session, target, intimacy=False, v2_only=False)
            intimacy = await _pool_size(session, target, intimacy=True, v2_only=False)
    return general == 5 and bool(intimacy)


async def _pool_size(
    session: AsyncSession,
    target: date,
    *,
    intimacy: bool,
    v2_only: bool,
) -> int:
    conditions = [
        Question.publish_date == target,
        Question.couple_id.is_(None),
        Question.intimacy.is_(intimacy),
        Question.disabled_at.is_(None),
    ]
    if v2_only:
        conditions.append(Question.interaction_version == 2)
    count = await session.scalar(select(func.count()).select_from(Question).where(*conditions))
    return int(count or 0)


async def curated_bank() -> list[CandidateQuestion] | None:
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


async def persist_pool(
    target: date,
    result: PipelineResult,
    settings: OllamaSettings,
    bank: list[CandidateQuestion],
    duration_ms: int,
    embedding_client: OllamaEmbeddingClient,
) -> None:
    async with SessionFactory() as session:
        candidates, database_quarantine, semantics = await _database_filtered_pool(
            session, target, result, bank, embedding_client
        )
        bank_ids = {item.client_id for item in bank}
        general_items = [item for item in candidates if not item.intimacy]
        order = {item.client_id: index for index, item in enumerate(general_items, start=1)}
        stored = [
            _question_record(target, item, bank_ids, order.get(item.client_id))
            for item in candidates
        ]
        session.add_all(stored)
        await session.flush()
        session.add_all(
            [
                concept_record(question, semantics[normalized_hash(question.prompt)])
                for question in stored
            ]
        )
        session.add(
            _generation_record(target, result, settings, stored, database_quarantine, duration_ms)
        )
        await session.commit()


def _question_record(
    target: date,
    item: CandidateQuestion,
    bank_ids: set[str],
    display_order: int | None,
) -> Question:
    return Question(
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
        display_order=display_order,
        source="curated" if item.client_id in bank_ids else "ollama",
        normalized_hash=normalized_hash(item.prompt),
    )


async def _database_filtered_pool(
    session: AsyncSession,
    target: date,
    result: PipelineResult,
    bank: list[CandidateQuestion],
    embedding_client: OllamaEmbeddingClient,
) -> tuple[
    list[CandidateQuestion],
    list[dict[str, object]],
    dict[str, CandidateSemantics],
]:
    selected, rejected, semantics = await _filter_database_duplicates(
        session, target, result, embedding_client
    )
    general = [item for item in selected if not item.intimacy][:5]
    intimacy = [item for item in selected if item.intimacy]
    await _fill_from_bank(
        session,
        target,
        bank,
        general,
        intimacy,
        selected,
        semantics,
        embedding_client,
    )
    if len(general) < 5 or not intimacy:
        raise RuntimeError("database duplicate gate exhausted the curated bank")
    return [*general[:5], *intimacy], rejected, semantics


async def _filter_database_duplicates(
    session: AsyncSession,
    target: date,
    result: PipelineResult,
    embedding_client: OllamaEmbeddingClient,
) -> tuple[
    list[CandidateQuestion],
    list[dict[str, object]],
    dict[str, CandidateSemantics],
]:
    selected: list[CandidateQuestion] = []
    rejected: list[dict[str, object]] = []
    semantics: dict[str, CandidateSemantics] = {}
    proposed = [*result.pool.general, *result.pool.intimacy_alternatives]
    for item in proposed:
        value = await candidate_semantics(embedding_client, item)
        same_batch = any(semantics_overlap(value, accepted) for accepted in semantics.values())
        if same_batch or await is_semantic_duplicate(session, target, item, value):
            reason = "batch_semantic_duplicate" if same_batch else "database_semantic_duplicate"
            rejected.append({"client_id": item.client_id, "reasons": [reason]})
        else:
            selected.append(item)
            semantics[normalized_hash(item.prompt)] = value
    return selected, rejected, semantics


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
    semantics: dict[str, CandidateSemantics],
    embedding_client: OllamaEmbeddingClient,
) -> None:
    used = {normalized_hash(item.prompt) for item in selected}
    for item in _rotated_bank(target, bank):
        if not _needs_bank_item(item, general, intimacy):
            continue
        if normalized_hash(item.prompt) in used:
            continue
        value = await candidate_semantics(embedding_client, item)
        same_batch = any(semantics_overlap(value, accepted) for accepted in semantics.values())
        if not same_batch and not await is_semantic_duplicate(session, target, item, value):
            (intimacy if item.intimacy else general).append(item)
            digest = normalized_hash(item.prompt)
            used.add(digest)
            semantics[digest] = value


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


async def record_seed_attempt(target: date, result: PipelineResult, duration_ms: int) -> None:
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


async def is_coverage_seed(target: date) -> bool:
    async with SessionFactory() as session:
        fallback_reason = await session.scalar(
            select(GenerationBatch.fallback_reason).where(
                GenerationBatch.publish_date == target
            )
        )
    return fallback_reason == "coverage_seed"


async def replace_unanswered_pool(target: date) -> bool:
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
