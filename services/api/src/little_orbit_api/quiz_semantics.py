"""Semantic concept memory for globally generated quiz questions."""

import math
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from little_orbit_ai.embeddings import OllamaEmbeddingClient
from little_orbit_ai.ollama import OllamaFailure
from little_orbit_ai.safety import normalize_question, normalized_hash
from little_orbit_ai.schemas import CandidateQuestion
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Question
from .quiz_intelligence_models import QuestionConcept

SEMANTIC_LOOKBACK_DAYS = 365
COSINE_DISTANCE_LIMIT = 0.16


@dataclass(frozen=True)
class CandidateSemantics:
    """Validated concept identity and optional pinned-model vectors."""

    family: str
    summary: str
    prompt_vector: list[float] | None
    concept_vector: list[float] | None
    model: str
    digest: str


def semantics_overlap(left: CandidateSemantics, right: CandidateSemantics) -> bool:
    """Reject one batch from disguising the same concept in another format."""

    if left.family == right.family:
        return True
    pairs = (
        (left.prompt_vector, right.prompt_vector),
        (left.concept_vector, right.concept_vector),
    )
    return any(
        first is not None
        and second is not None
        and _cosine_distance(first, second) <= COSINE_DISTANCE_LIMIT
        for first, second in pairs
    )


async def candidate_semantics(
    client: OllamaEmbeddingClient,
    item: CandidateQuestion,
) -> CandidateSemantics:
    """Derive stable metadata and embed it without exposing any user data."""

    family = item.concept_family or derived_family(item)
    summary = item.concept_summary or item.prompt.rstrip("?")
    try:
        vectors = await client.embed(
            [f"search_document: {item.prompt}", f"search_document: {summary}"]
        )
        prompt_vector, concept_vector = vectors
    except OllamaFailure:
        prompt_vector, concept_vector = None, None
    return CandidateSemantics(
        family=family,
        summary=summary[:180],
        prompt_vector=prompt_vector,
        concept_vector=concept_vector,
        model=client.settings.model,
        digest=client.settings.manifest_digest,
    )


async def is_semantic_duplicate(
    session: AsyncSession,
    target: date,
    item: CandidateQuestion,
    semantics: CandidateSemantics,
) -> bool:
    """Reject repeated wording or concepts over the full 365-day memory."""

    start = target - timedelta(days=SEMANTIC_LOOKBACK_DAYS)
    wording_match = await session.scalar(
        select(func.count())
        .select_from(Question)
        .where(
            Question.couple_id.is_(None),
            Question.publish_date >= start,
            Question.publish_date < target,
            or_(
                Question.normalized_hash == normalized_hash(item.prompt),
                func.similarity(Question.prompt, item.prompt) >= 0.82,
            ),
        )
    )
    if wording_match:
        return True
    conditions = [QuestionConcept.concept_family == semantics.family]
    if semantics.prompt_vector is not None:
        conditions.append(
            QuestionConcept.prompt_embedding.cosine_distance(
                semantics.prompt_vector
            )
            <= COSINE_DISTANCE_LIMIT
        )
    if semantics.concept_vector is not None:
        conditions.append(
            QuestionConcept.concept_embedding.cosine_distance(
                semantics.concept_vector
            )
            <= COSINE_DISTANCE_LIMIT
        )
    concept_match = await session.scalar(
        select(func.count())
        .select_from(QuestionConcept)
        .join(Question, Question.id == QuestionConcept.question_id)
        .where(
            Question.publish_date >= start,
            Question.publish_date < target,
            Question.couple_id.is_(None),
            or_(*conditions),
        )
    )
    return bool(concept_match)


def concept_record(question: Question, value: CandidateSemantics) -> QuestionConcept:
    """Build persistence only after the corresponding question has an ID."""

    return QuestionConcept(
        question_id=question.id,
        concept_family=value.family,
        concept_summary=value.summary,
        prompt_embedding=value.prompt_vector,
        concept_embedding=value.concept_vector,
        embedding_model=value.model,
        embedding_digest=value.digest,
        embedded_at=(datetime.now(UTC) if value.prompt_vector is not None else None),
    )


def derived_family(item: CandidateQuestion) -> str:
    words = [
        word
        for word in normalize_question(item.prompt).split()
        if word not in {"what", "which", "would", "could", "your", "together", "about"}
    ]
    slug = re.sub(r"[^a-z0-9-]", "", "-".join([item.category.value, *words[:4]]))
    return slug[:80] or f"{item.category.value}-question"


def _cosine_distance(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return math.inf
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return math.inf
    similarity = sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )
    return 1.0 - max(-1.0, min(1.0, similarity))
