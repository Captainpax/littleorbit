"""Pure RC10 Smooch vocabulary, message, rate, and calendar helpers."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

EMOJIS = ("😘", "😍", "🤭", "😈", "🔥", "👀", "💖", "🐻", "🍑")
PHRASE_KEYS = (
    "thinking_about_you",
    "sent_a_smooch",
    "little_love",
    "nudged_your_orbit",
    "make_you_smile",
    "tiny_spark",
)
HOURLY_LIMIT = 5


def choose_phrase(operation_id: UUID) -> str:
    """Choose stable wording so an idempotent retry cannot change its meaning."""

    return PHRASE_KEYS[operation_id.int % len(PHRASE_KEYS)]


def retry_after_seconds(sent_at: list[datetime], now: datetime) -> int:
    """Return the wait until one rolling-hour slot opens, or zero."""

    recent = sorted(item for item in sent_at if item > now - timedelta(hours=1))
    if len(recent) < HOURLY_LIMIT:
        return 0
    return max(1, int((recent[0] + timedelta(hours=1) - now).total_seconds()) + 1)


def week_start(value: datetime, timezone_name: str) -> date:
    """Return Monday for an instant in the couple's IANA home timezone."""

    local_day = value.astimezone(ZoneInfo(timezone_name)).date()
    return local_day - timedelta(days=local_day.weekday())


def week_bounds_utc(start: date, timezone_name: str) -> tuple[datetime, datetime]:
    """Convert one local Monday boundary to a DST-safe half-open UTC range."""

    zone = ZoneInfo(timezone_name)
    local_start = datetime.combine(start, time.min, zone)
    local_end = datetime.combine(start + timedelta(days=7), time.min, zone)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)
