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

from .ai_work_queue import AiWorkLease, AiWorkLeaseExpired, require_current_lease
from .clock import SystemClock
from .database import SessionFactory
from .models import Question
from .quiz_feedback_retention import LINKED_RETENTION, aggregate_feedback_week
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


async def learn_feedback_week(
    week_start: date,
    client: OllamaClient,
    *,
    lease: AiWorkLease | None = None,
) -> str:
    """Learn and atomically activate one bounded policy, once per UTC week."""

    now = SystemClock().now()
    run_key = f"learn:{week_start.isoformat()}"
    if not await claim_ai_run(run_key, "learning", now, lease=lease):
        if await ai_run_is_finished(run_key):
            return "already_completed"
        raise RuntimeError("AI learning run is already active")
    try:
        signals = await _collect_learning_signals(week_start, now, lease)
        if not signals:
            await _advance_learning_cursor(now, lease)
            await finish_ai_run(
                run_key,
                "fallback",
                {"reason": "no_thresholded_feedback"},
                lease=lease,
            )
            return "no_feedback"
        policy = await client.learn(build_learning_prompt(signals))
        rejection_reasons = policy_rejection_reasons(policy, signals)
        if rejection_reasons:
            version = await _reject_policy(
                policy, len(signals), rejection_reasons, now, lease
            )
            await finish_ai_run(
                run_key,
                "fallback",
                {"reason": "evaluation_rejected", "reasons": list(rejection_reasons)},
                version,
                lease,
            )
            return "rejected"
        version = await _activate_policy(policy, len(signals), now, lease)
        await _advance_learning_cursor(now, lease)
        await finish_ai_run(
            run_key,
            "passed",
            {"signal_count": len(signals), "policy_version": version},
            version,
            lease,
        )
        return "passed"
    except OllamaFailure:
        await finish_ai_run(
            run_key, "fallback", {"reason": "model_unavailable"}, lease=lease
        )
        return "fallback"
    except Exception:
        await finish_ai_run(
            run_key, "failed", {"reason": "internal_failure"}, lease=lease
        )
        raise


async def _collect_learning_signals(
    week_start: date, now: datetime, lease: AiWorkLease | None
) -> list[LearningQuestionSignal]:
    """Aggregate and read thresholded signals under the exact queue lease."""

    async with SessionFactory() as session:
        await require_current_lease(session, lease)
        cursor = await _learning_cursor(session, week_start, now)
        await _aggregate_since(session, cursor.feedback_updated_through, now)
        signals = await _learning_signals(
            session, cursor.feedback_updated_through, now
        )
        await session.commit()
    return signals


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
    eligible_reviews = {
        (item.question_id, item.week_start) for item in aggregates
    }
    first_week = min(item.week_start for item in aggregates)
    last_week = max(item.week_start for item in aggregates)
    review_start = datetime.combine(first_week, time.min, tzinfo=UTC)
    review_end = datetime.combine(
        last_week + timedelta(days=7), time.min, tzinfo=UTC
    )
    review_rows = await session.execute(
        select(
            QuestionFeedback.question_id,
            QuestionFeedback.updated_at,
            QuestionFeedback.sanitized_review,
        ).where(
            QuestionFeedback.question_id.in_(question_ids),
            QuestionFeedback.updated_at >= review_start,
            QuestionFeedback.updated_at < review_end,
            QuestionFeedback.updated_at < through,
            QuestionFeedback.review_status == "accepted",
            QuestionFeedback.sanitized_review.is_not(None),
        )
    )
    reviews = _bucket_learning_reviews(list(review_rows.tuples()), eligible_reviews)
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
                reviews=reviews[(question.id, aggregate.week_start)],
            )
        )
    return result


def _bucket_learning_reviews(
    rows: list[tuple[UUID, datetime, str | None]],
    eligible: set[tuple[UUID, date]],
) -> dict[tuple[UUID, date], list[str]]:
    """Keep review text inside the exact K-anonymous UTC aggregate week."""

    reviews: dict[tuple[UUID, date], list[str]] = defaultdict(list)
    for question_id, updated_at, review in rows:
        review_date = updated_at.astimezone(UTC).date()
        week_start = review_date - timedelta(days=review_date.weekday())
        key = (question_id, week_start)
        if key in eligible and review is not None and len(reviews[key]) < 20:
            reviews[key].append(review)
    return reviews


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
    """Reconcile cursor-pending and still-attributable UTC feedback weeks."""

    earliest = min(since, now - LINKED_RETENTION)
    monday = earliest.date() - timedelta(days=earliest.weekday())
    final = now.date() - timedelta(days=now.weekday())
    while monday <= final:
        await aggregate_feedback_week(session, monday, now)
        monday += timedelta(days=7)


async def _advance_learning_cursor(
    through: datetime, lease: AiWorkLease | None = None
) -> None:
    """Advance only after a no-op or successfully activated policy."""

    async with SessionFactory() as session:
        await require_current_lease(session, lease)
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


async def _activate_policy(
    policy: LearningPolicy,
    signal_count: int,
    now: datetime,
    lease: AiWorkLease | None = None,
) -> int:
    digest = hashlib.sha256(
        json.dumps(policy.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    async with SessionFactory() as session:
        await require_current_lease(session, lease)
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
    lease: AiWorkLease | None = None,
) -> int:
    """Preserve safe audit metadata without activating failed learned guidance."""

    async with SessionFactory() as session:
        await require_current_lease(session, lease)
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


async def claim_ai_run(
    run_key: str,
    kind: str,
    now: datetime,
    *,
    lease: AiWorkLease | None = None,
) -> bool:
    """Claim one idempotent scheduled run, taking over only after two hours."""

    async with SessionFactory() as session:
        await require_current_lease(session, lease)
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


async def ai_run_is_finished(run_key: str) -> bool:
    """Return whether one idempotent run has a durable terminal outcome."""

    async with SessionFactory() as session:
        status = await session.scalar(
            select(AiRun.status).where(AiRun.run_key == run_key)
        )
    return status in {"passed", "fallback"}


async def finish_ai_run(
    run_key: str,
    status: str,
    summary: dict[str, object],
    policy_version: int | None = None,
    lease: AiWorkLease | None = None,
) -> bool:
    """Finish one claimed run with content-free operational metadata."""

    async with SessionFactory() as session:
        try:
            await require_current_lease(session, lease)
        except AiWorkLeaseExpired:
            return False
        record = await session.scalar(
            select(AiRun).where(AiRun.run_key == run_key).with_for_update()
        )
        if record is None:
            return False
        record.status = status
        record.summary_json = summary
        record.policy_version = policy_version
        record.finished_at = SystemClock().now()
        await session.commit()
    return True
