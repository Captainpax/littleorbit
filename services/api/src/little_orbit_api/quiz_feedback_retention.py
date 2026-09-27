"""Bounded retention and identity-free weekly quiz feedback aggregation."""

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Question
from .quiz_intelligence_models import (
    AnonymousQuestionReview,
    FeedbackWeeklyAggregate,
    QuestionFeedback,
    QuestionFeedbackOperation,
)

LINKED_RETENTION = timedelta(days=30)
ANONYMOUS_RETENTION = timedelta(days=90)
MINIMUM_AGGREGATE_ACCOUNTS = 5


async def enforce_feedback_retention(session: AsyncSession, now: datetime) -> None:
    """Unlink expired feedback, then remove all review text by its hard deadline."""

    expired = list(
        await session.scalars(
            select(QuestionFeedback)
            .where(QuestionFeedback.editable_until <= now)
            .with_for_update(skip_locked=True)
        )
    )
    for record in expired:
        hard_expiry = record.editable_until + (ANONYMOUS_RETENTION - LINKED_RETENTION)
        if hard_expiry > now:
            session.add(
                AnonymousQuestionReview(
                    question_id=record.question_id,
                    stars=record.stars,
                    tags=list(record.tags),
                    sanitized_review=(
                        record.sanitized_review
                        if record.review_status == "accepted"
                        else None
                    ),
                    week_start=_monday(record.updated_at.date()),
                    expires_at=hard_expiry,
                )
            )
        await session.delete(record)
    await session.execute(
        delete(QuestionFeedbackOperation).where(
            QuestionFeedbackOperation.created_at <= now - LINKED_RETENTION
        )
    )
    await session.execute(
        delete(AnonymousQuestionReview).where(
            AnonymousQuestionReview.expires_at <= now
        )
    )


async def aggregate_feedback_week(
    session: AsyncSession,
    week_start: date,
    now: datetime,
) -> int:
    """Reconcile threshold-ready, identity-free totals for one UTC feedback week."""

    start = datetime.combine(week_start, time.min, tzinfo=UTC)
    end = start + timedelta(days=7)
    rows = await _feedback_rows(session, start, end)
    grouped: dict[UUID, list[QuestionFeedback]] = defaultdict(list)
    for feedback, question in rows:
        grouped[question.id].append(feedback)
    eligible = {
        question_id: (records, len({record.account_id for record in records}))
        for question_id, records in grouped.items()
        if len({record.account_id for record in records}) >= MINIMUM_AGGREGATE_ACCOUNTS
    }
    existing = {
        record.question_id: record
        for record in await session.scalars(
            select(FeedbackWeeklyAggregate)
            .where(FeedbackWeeklyAggregate.week_start == week_start)
            .with_for_update()
        )
    }
    for question_id, aggregate in existing.items():
        if question_id not in eligible:
            await session.delete(aggregate)
    changed = 0
    for question_id, (records, account_count) in eligible.items():
        changed += int(
            await _upsert_aggregate(
                session,
                question_id,
                week_start,
                now,
                records,
                account_count,
                existing.get(question_id),
            )
        )
    return changed


async def _feedback_rows(
    session: AsyncSession, start: datetime, end: datetime
) -> list[tuple[QuestionFeedback, Question]]:
    result = await session.execute(
        select(QuestionFeedback, Question)
        .join(Question, Question.id == QuestionFeedback.question_id)
        .where(
            QuestionFeedback.updated_at >= start,
            QuestionFeedback.updated_at < end,
            Question.couple_id.is_(None),
        )
        .with_for_update(of=QuestionFeedback)
    )
    return list(result.tuples())


async def _upsert_aggregate(
    session: AsyncSession,
    question_id: object,
    week_start: date,
    now: datetime,
    records: list[QuestionFeedback],
    account_count: int,
    aggregate: FeedbackWeeklyAggregate | None,
) -> bool:
    tag_counts = Counter(tag for record in records for tag in record.tags)
    values = {
        "rating_count": len(records),
        "distinct_accounts": account_count,
        "score_sum": sum(record.stars for record in records),
        "tag_counts": dict(sorted(tag_counts.items())),
        "themes": [
            tag
            for tag, _count in sorted(
                tag_counts.items(), key=lambda item: (-item[1], item[0])
            )[:5]
        ],
    }
    if aggregate is None:
        session.add(
            FeedbackWeeklyAggregate(
                question_id=question_id,
                week_start=week_start,
                created_at=now,
                updated_at=now,
                **values,
            )
        )
        return True
    source_changed = any(
        record.updated_at > aggregate.updated_at for record in records
    )
    values_changed = any(
        getattr(aggregate, field) != value for field, value in values.items()
    )
    if not source_changed and not values_changed:
        return False
    for field, value in values.items():
        setattr(aggregate, field, value)
    aggregate.updated_at = now
    return True


def _monday(value: date) -> date:
    return value - timedelta(days=value.weekday())
