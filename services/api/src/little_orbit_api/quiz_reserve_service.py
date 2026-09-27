"""Immutable one-year reserve synchronization and one-time consumption."""

from dataclasses import dataclass
from datetime import date

from little_orbit_ai.reserve import (
    BANK_VERSION,
    GENERAL_COUNT,
    INTIMACY_COUNT,
    load_reviewed_reserve,
)
from little_orbit_ai.schemas import (
    CandidateQuestion,
    Category,
    IconKey,
    QuestionDepth,
    QuestionKind,
    ThemeRole,
)
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .database import SessionFactory
from .quiz_intelligence_models import QuestionReserve

RESERVE_PREFIX = f"r{BANK_VERSION}-"


@dataclass(frozen=True)
class ReserveHealth:
    """Content-free reserve capacity for operations and alerting."""

    general_available: int
    intimacy_available: int
    expected_general: int = GENERAL_COUNT
    expected_intimacy: int = INTIMACY_COUNT

    @property
    def complete(self) -> bool:
        return (
            self.general_available == self.expected_general
            and self.intimacy_available == self.expected_intimacy
        )


async def sync_question_reserve() -> ReserveHealth:
    """Insert missing immutable reserve rows; never overwrite consumed bytes."""

    existing = await reserve_health(include_consumed=True)
    if existing.complete:
        return await reserve_health()
    entries = load_reviewed_reserve()
    now = SystemClock().now()
    rows = [
        {
            "stable_key": item.candidate.client_id,
            "bank_version": BANK_VERSION,
            "concept_family": item.candidate.concept_family,
            "concept_summary": item.candidate.concept_summary,
            "depth": item.candidate.depth.value,
            "theme_tags": item.candidate.theme_tags,
            "content_hash": item.content_hash,
            "review_tier": item.review_tier,
            "kind": item.candidate.kind.value,
            "prompt": item.candidate.prompt,
            "category": item.candidate.category.value,
            "intimacy": item.candidate.intimacy,
            "options": item.candidate.options,
            "option_icons": [value.value for value in item.candidate.option_icons],
            "scale_low_label": item.candidate.scale_low_label,
            "scale_high_label": item.candidate.scale_high_label,
            "created_at": now,
        }
        for item in entries
    ]
    async with SessionFactory() as session:
        for start in range(0, len(rows), 250):
            statement = insert(QuestionReserve).values(rows[start : start + 250])
            await session.execute(statement.on_conflict_do_nothing(index_elements=["stable_key"]))
        await session.commit()
    health = await reserve_health(include_consumed=True)
    if not health.complete:
        raise RuntimeError("immutable quiz reserve failed completeness verification")
    return await reserve_health()


async def available_reserve() -> list[CandidateQuestion]:
    """Load unused reviewed entries in their deterministic daily-diverse order."""

    async with SessionFactory() as session:
        records = list(
            await session.scalars(
                select(QuestionReserve)
                .where(
                    QuestionReserve.bank_version == BANK_VERSION,
                    QuestionReserve.consumed_at.is_(None),
                )
                .order_by(QuestionReserve.stable_key)
            )
        )
    return [_candidate(item) for item in records]


async def consume_selected_reserve(
    session: AsyncSession, target: date, selected: list[CandidateQuestion]
) -> None:
    """Atomically consume only reserve entries actually persisted for one day."""

    keys = [item.client_id for item in selected if item.client_id.startswith(RESERVE_PREFIX)]
    if not keys:
        return
    result = await session.execute(
        update(QuestionReserve)
        .where(
            QuestionReserve.stable_key.in_(keys),
            QuestionReserve.consumed_at.is_(None),
        )
        .values(consumed_at=SystemClock().now(), last_used_on=target)
    )
    if result.rowcount != len(set(keys)):
        raise RuntimeError("quiz reserve entry was already consumed")


async def reserve_health(*, include_consumed: bool = False) -> ReserveHealth:
    """Count only the current immutable bank without exposing question text."""

    async with SessionFactory() as session:
        base = [QuestionReserve.bank_version == BANK_VERSION]
        if not include_consumed:
            base.append(QuestionReserve.consumed_at.is_(None))
        general = await session.scalar(
            select(func.count()).select_from(QuestionReserve).where(*base, QuestionReserve.intimacy.is_(False))
        )
        intimacy = await session.scalar(
            select(func.count()).select_from(QuestionReserve).where(*base, QuestionReserve.intimacy.is_(True))
        )
    return ReserveHealth(int(general or 0), int(intimacy or 0))


def _candidate(record: QuestionReserve) -> CandidateQuestion:
    return CandidateQuestion(
        client_id=record.stable_key,
        kind=QuestionKind(record.kind),
        prompt=record.prompt,
        category=Category(record.category),
        intimacy=record.intimacy,
        options=record.options,
        option_icons=[IconKey(value) for value in record.option_icons],
        scale_low_label=record.scale_low_label,
        scale_high_label=record.scale_high_label,
        concept_family=record.concept_family,
        concept_summary=record.concept_summary,
        depth=QuestionDepth(record.depth),
        theme_role=ThemeRole.VARIETY,
        theme_tags=record.theme_tags,
    )
