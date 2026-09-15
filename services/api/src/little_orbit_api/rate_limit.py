"""PostgreSQL-backed fixed-window throttles with hashed, expiring subjects."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .config import Settings, get_settings
from .database import SessionFactory
from .models import RateLimitBucket
from .security import hash_token


@dataclass(frozen=True)
class RateLimitRule:
    """One fixed-window limit; ``subject`` is hashed before persistence."""

    scope: str
    subject: str
    limit: int
    window: timedelta


@dataclass(frozen=True)
class RateLimitDecision:
    """Result of applying ordered limits to one request."""

    allowed: bool
    blocked_scope: str | None = None


async def consume_rate_limits(
    rules: list[RateLimitRule],
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> RateLimitDecision:
    """Commit counters independently so rejected application work cannot erase attempts."""

    current = now or SystemClock().now()
    runtime_settings = settings or get_settings()
    async with SessionFactory() as session:
        decision = await _consume_rules(session, rules, current, runtime_settings)
        await session.commit()
        return decision


async def purge_rate_limit_state(session: AsyncSession, now: datetime) -> None:
    """Remove inactive privacy-minimized counters after their retention ceiling."""

    await session.execute(
        delete(RateLimitBucket).where(
            RateLimitBucket.updated_at <= now - timedelta(hours=24)
        )
    )


async def _consume_rules(
    session: AsyncSession,
    rules: list[RateLimitRule],
    now: datetime,
    settings: Settings,
) -> RateLimitDecision:
    """Stop before high-cardinality subjects after an IP bucket blocks the request."""

    for rule in rules:
        if not await _consume_rule(session, rule, now, settings):
            return RateLimitDecision(False, rule.scope)
    return RateLimitDecision(True)


async def _consume_rule(
    session: AsyncSession,
    rule: RateLimitRule,
    now: datetime,
    settings: Settings,
) -> bool:
    digest = rate_limit_subject(rule.scope, rule.subject, settings)
    await session.execute(
        delete(RateLimitBucket).where(
            RateLimitBucket.scope == rule.scope,
            RateLimitBucket.window_started_at <= now - rule.window,
        )
    )
    statement = (
        insert(RateLimitBucket)
        .values(
            scope=rule.scope,
            subject_hash=digest,
            window_started_at=now,
            count=1,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["scope", "subject_hash"],
            set_={
                "count": func.least(RateLimitBucket.count + 1, rule.limit + 1),
                "updated_at": now,
            },
        )
        .returning(RateLimitBucket.count)
    )
    count = await session.scalar(statement)
    return count is not None and count <= rule.limit


def rate_limit_subject(scope: str, subject: str, settings: Settings) -> str:
    """Digest a subject with domain separation before it reaches persistence."""

    pepper = settings.token_pepper.get_secret_value()
    return hash_token(f"rate-limit:{scope}:{subject}", pepper)


def request_rules(
    action: str,
    client_ip: str,
    subject: str,
    *,
    ip_limit: int,
    subject_limit: int,
    window: timedelta,
) -> list[RateLimitRule]:
    """Build IP-first rules so blocked hosts cannot grow subject cardinality."""

    return [
        RateLimitRule(f"{action}:ip", client_ip, ip_limit, window),
        RateLimitRule(f"{action}:subject", subject, subject_limit, window),
    ]
