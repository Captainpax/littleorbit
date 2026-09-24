"""Bounded retention and identity-free weekly quiz feedback aggregation."""

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta

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
    """Upsert threshold-ready, identity-free totals for one UTC feedback week."""

    start = datetime.combine(week_start, time.min, tzinfo=UTC)
    end = start + timedelta(days=7)
    rows = await _feedback_rows(session, start, end)
    grouped: dict[object, list[QuestionFeedback]] = defaultdict(list)
    for feedback, question in rows:
        grouped[question.id].append(feedback)
    changed = 0
    for question_id, records in grouped.items():
        accounts = {record.account_id for record in records}
        if len(accounts) < MINIMUM_AGGREGATE_ACCOUNTS:
            continue
        await _upsert_aggregate(session, question_id, week_start, now, records, len(accounts))
        changed += 1
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
    )
    return list(result.tuples())


async def _upsert_aggregate(
    session: AsyncSession,
    question_id: object,
    week_start: date,
    now: datetime,
    records: list[QuestionFeedback],
    account_count: int,
) -> None:
    tag_counts = Counter(tag for record in records for tag in record.tags)
    aggregate = await session.scalar(
        select(FeedbackWeeklyAggregate)
        .where(
            FeedbackWeeklyAggregate.question_id == question_id,
            FeedbackWeeklyAggregate.week_start == week_start,
        )
        .with_for_update()
    )
    values = {
        "rating_count": len(records),
        "distinct_accounts": account_count,
        "score_sum": sum(record.stars for record in records),
        "tag_counts": dict(sorted(tag_counts.items())),
        "themes": [tag for tag, _ in tag_counts.most_common(5)],
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
        return
    for field, value in values.items():
        setattr(aggregate, field, value)
    aggregate.updated_at = now


def _monday(value: date) -> date:
    return value - timedelta(days=value.weekday())
