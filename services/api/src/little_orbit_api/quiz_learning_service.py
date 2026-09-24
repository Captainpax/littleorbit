"""Saturday learning from consented, thresholded quiz feedback."""

import hashlib
import json
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from little_orbit_ai.learning_eval import policy_rejection_reasons
from little_orbit_ai.ollama import OllamaClient, OllamaFailure
from little_orbit_ai.prompt import build_learning_prompt
from little_orbit_ai.schemas import (
    CandidateQuestion,
    Category,
    IconKey,
    LearningPolicy,
    LearningQuestionSignal,
    QuestionKind,
)
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .database import SessionFactory
from .models import Question
from .quiz_feedback_retention import aggregate_feedback_week
from .quiz_intelligence_models import (
    AiLearningCursor,
    AiPolicyVersion,
    AiRun,
    FeedbackWeeklyAggregate,
    QuestionConcept,
    QuestionFeedback,
)
from .quiz_semantics import derived_family

RUN_TAKEOVER_AFTER = timedelta(hours=2)


async def learn_feedback_week(week_start: date, client: OllamaClient) -> str:
    """Learn and atomically activate one bounded policy, once per UTC week."""

    now = SystemClock().now()
    run_key = f"learn:{week_start.isoformat()}"
    if not await claim_ai_run(run_key, "learning", now):
        return "already_claimed"
    try:
        async with SessionFactory() as session:
            cursor = await _learning_cursor(session, week_start, now)
            await _aggregate_since(session, cursor.feedback_updated_through, now)
            signals = await _learning_signals(
                session, cursor.feedback_updated_through, now
            )
            await session.commit()
        if not signals:
            await _advance_learning_cursor(now)
            await finish_ai_run(run_key, "fallback", {"reason": "no_thresholded_feedback"})
            return "no_feedback"
        policy = await client.learn(build_learning_prompt(signals))
        rejection_reasons = policy_rejection_reasons(policy, signals)
        if rejection_reasons:
            version = await _reject_policy(policy, len(signals), rejection_reasons, now)
            await finish_ai_run(
                run_key,
                "fallback",
                {"reason": "evaluation_rejected", "reasons": list(rejection_reasons)},
                version,
            )
            return "rejected"
        version = await _activate_policy(policy, len(signals), now)
        await _advance_learning_cursor(now)
        await finish_ai_run(
            run_key,
            "passed",
            {"signal_count": len(signals), "policy_version": version},
            version,
        )
        return "passed"
    except OllamaFailure:
        await finish_ai_run(run_key, "fallback", {"reason": "model_unavailable"})
        return "fallback"
    except Exception:
        await finish_ai_run(run_key, "failed", {"reason": "internal_failure"})
        raise


async def active_learning_policy() -> LearningPolicy | None:
    """Return only the single transactionally active policy."""

    async with SessionFactory() as session:
        record = await session.scalar(
            select(AiPolicyVersion)
            .where(AiPolicyVersion.status == "active")
            .order_by(AiPolicyVersion.version.desc())
            .limit(1)
        )
    return LearningPolicy.model_validate(record.policy_json) if record else None


async def _learning_signals(
    session: AsyncSession, changed_after: datetime, through: datetime
) -> list[LearningQuestionSignal]:
    aggregates = list(
        await session.scalars(
            select(FeedbackWeeklyAggregate).where(
                FeedbackWeeklyAggregate.distinct_accounts >= 5,
                FeedbackWeeklyAggregate.updated_at > changed_after,
                FeedbackWeeklyAggregate.updated_at <= through,
            )
        )
    )
    if not aggregates:
        return []
    question_ids = [item.question_id for item in aggregates]
    questions = {
        item.id: item
        for item in await session.scalars(
            select(Question).where(Question.id.in_(question_ids))
        )
    }
    concepts = {
        item.question_id: item
        for item in await session.scalars(
            select(QuestionConcept).where(QuestionConcept.question_id.in_(question_ids))
        )
    }
    start = max(changed_after, through - timedelta(days=30))
    reviews: dict[UUID, list[str]] = defaultdict(list)
    review_rows = await session.execute(
        select(QuestionFeedback.question_id, QuestionFeedback.sanitized_review).where(
            QuestionFeedback.question_id.in_(question_ids),
            QuestionFeedback.updated_at >= start,
            QuestionFeedback.updated_at < through,
            QuestionFeedback.review_status == "accepted",
            QuestionFeedback.sanitized_review.is_not(None),
        )
    )
    for question_id, review in review_rows:
        if review is not None and len(reviews[question_id]) < 20:
            reviews[question_id].append(review)
    result: list[LearningQuestionSignal] = []
    for aggregate in aggregates:
        question = questions.get(aggregate.question_id)
        if question is None:
            continue
        concept = concepts.get(question.id)
        family = concept.concept_family if concept else _fallback_family(question)
        result.append(
            LearningQuestionSignal(
                concept_family=family,
                category=Category(question.category),
                rating_count=aggregate.rating_count,
                average_stars=aggregate.score_sum / aggregate.rating_count,
                tag_counts=aggregate.tag_counts,
                reviews=reviews[question.id],
            )
        )
    return result


async def _learning_cursor(
    session: AsyncSession, week_start: date, now: datetime
) -> AiLearningCursor:
    """Lock or create the carry-forward watermark without advancing it early."""

    record = await session.get(AiLearningCursor, "quiz-feedback", with_for_update=True)
    if record is not None:
        return record
    initial = datetime.combine(week_start, time.min, tzinfo=UTC)
    record = AiLearningCursor(
        name="quiz-feedback",
        feedback_updated_through=max(initial, now - timedelta(days=30)),
        last_run_at=now,
    )
    session.add(record)
    await session.flush()
    return record


async def _aggregate_since(session: AsyncSession, since: datetime, now: datetime) -> None:
    """Recompute every touched UTC week so late edits become eligible once thresholded."""

    monday = since.date() - timedelta(days=since.weekday())
    final = now.date() - timedelta(days=now.weekday())
    while monday <= final:
        await aggregate_feedback_week(session, monday, now)
        monday += timedelta(days=7)


async def _advance_learning_cursor(through: datetime) -> None:
    """Advance only after a no-op or successfully activated policy."""

    async with SessionFactory() as session:
        record = await session.get(AiLearningCursor, "quiz-feedback", with_for_update=True)
        if record is None:
            return
        if through > record.feedback_updated_through:
            record.feedback_updated_through = through
        record.last_run_at = through
        await session.commit()


def _fallback_family(question: Question) -> str:
    item = CandidateQuestion(
        client_id="stored-question",
        kind=QuestionKind(question.kind),
        prompt=question.prompt,
        category=Category(question.category),
        intimacy=question.intimacy,
        options=question.options,
        option_icons=[IconKey(value) for value in question.option_icons],
        scale_low_label=question.scale_low_label,
        scale_high_label=question.scale_high_label,
    )
    return derived_family(item)


async def _activate_policy(policy: LearningPolicy, signal_count: int, now: datetime) -> int:
    digest = hashlib.sha256(
        json.dumps(policy.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    async with SessionFactory() as session:
        await session.execute(text("SELECT pg_advisory_xact_lock(12002026)"))
        await session.execute(
            update(AiPolicyVersion)
            .where(AiPolicyVersion.status == "active")
            .values(status="superseded")
        )
        current = await session.scalar(select(func.max(AiPolicyVersion.version)))
        version = int(current or 0) + 1
        session.add(
            AiPolicyVersion(
                version=version,
                status="active",
                policy_json=policy.model_dump(mode="json"),
                evaluation_json={
                    "schema_valid": True,
                    "thresholded_signal_count": signal_count,
                    "policy_sha256": digest,
                },
                created_at=now,
                activated_at=now,
            )
        )
        await session.commit()
    return version


async def _reject_policy(
    policy: LearningPolicy,
    signal_count: int,
    reasons: tuple[str, ...],
    now: datetime,
) -> int:
    """Preserve safe audit metadata without activating failed learned guidance."""

    async with SessionFactory() as session:
        await session.execute(text("SELECT pg_advisory_xact_lock(12002026)"))
        current = await session.scalar(select(func.max(AiPolicyVersion.version)))
        version = int(current or 0) + 1
        session.add(
            AiPolicyVersion(
                version=version,
                status="rejected",
                policy_json=policy.model_dump(mode="json"),
                evaluation_json={
                    "schema_valid": True,
                    "thresholded_signal_count": signal_count,
                    "reasons": list(reasons),
                },
                created_at=now,
            )
        )
        await session.commit()
    return version


async def claim_ai_run(run_key: str, kind: str, now: datetime) -> bool:
    """Claim one idempotent scheduled run, taking over only after two hours."""

    async with SessionFactory() as session:
        inserted = await session.scalar(
            insert(AiRun)
            .values(
                run_key=run_key,
                kind=kind,
                status="running",
                summary_json={},
                started_at=now,
            )
            .on_conflict_do_nothing(index_elements=[AiRun.run_key])
            .returning(AiRun.id)
        )
        if inserted is not None:
            await session.commit()
            return True
        record = await session.scalar(
            select(AiRun).where(AiRun.run_key == run_key).with_for_update()
        )
        if record is None:
            raise RuntimeError("AI run conflict did not preserve its row")
        if record.status in {"passed", "fallback"}:
            return False
        if record.status == "running" and record.started_at > now - RUN_TAKEOVER_AFTER:
            return False
        record.status = "running"
        record.started_at = now
        record.finished_at = None
        record.summary_json = {}
        await session.commit()
    return True


async def finish_ai_run(
    run_key: str,
    status: str,
    summary: dict[str, object],
    policy_version: int | None = None,
) -> None:
    """Finish one claimed run with content-free operational metadata."""

    async with SessionFactory() as session:
        record = await session.scalar(
            select(AiRun).where(AiRun.run_key == run_key).with_for_update()
        )
        if record is None:
            return
        record.status = status
        record.summary_json = summary
        record.policy_version = policy_version
        record.finished_at = SystemClock().now()
        await session.commit()
