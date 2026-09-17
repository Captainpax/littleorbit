"""Pure chronological proximity decisions for together-time estimates."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from math import asin, cos, radians, sin, sqrt
from typing import Literal

EARTH_RADIUS_M = 6_371_000.0
MAX_MUTUAL_EVIDENCE_AGE = timedelta(minutes=5)
MAX_SAMPLE_SKEW = timedelta(minutes=5)
MAX_COUNTED_INTERVAL = timedelta(minutes=5)
RECOMPUTE_HORIZON = timedelta(hours=23, minutes=45)
RAW_LOCATION_RETENTION = timedelta(hours=24)
PRIVACY_MAINTENANCE_INTERVAL = timedelta(minutes=5)

EvidenceState = Literal[
    "waiting_for_partner",
    "nearby",
    "apart",
    "poor_accuracy",
    "stale",
]
CountingState = Literal[
    "sharing_disabled",
    "waiting_for_partner",
    "confirming",
    "nearby",
    "apart",
    "poor_accuracy",
    "stale",
]


@dataclass(frozen=True)
class Point:
    """One coordinate and its reported horizontal accuracy."""

    latitude: float
    longitude: float
    accuracy_m: float


@dataclass(frozen=True)
class ProximityDecision:
    """Distance bounds and whether a pair can be counted together."""

    measured_distance_m: float
    minimum_distance_m: float
    maximum_distance_m: float
    together: bool
    uncertain: bool


@dataclass(frozen=True)
class TimedPoint:
    """One deduplicated sample used by the deterministic interval algorithm."""

    sample_id: str
    recorded_at: datetime
    point: Point


@dataclass(frozen=True)
class EvidenceAnchor:
    """One chronological two-stream decision after all observations at an instant."""

    recorded_at: datetime
    state: EvidenceState
    measured_distance_m: float | None
    left: TimedPoint | None
    right: TimedPoint | None


@dataclass(frozen=True)
class MinuteEstimate:
    """Coordinate-free overlap within one UTC minute."""

    bucket_start: datetime
    duration_seconds: int
    estimated_distance_m: float


@dataclass(frozen=True)
class ProximityTimeline:
    """Chronological evidence anchors and their coordinate-free estimates."""

    anchors: tuple[EvidenceAnchor, ...]
    estimates: tuple[MinuteEstimate, ...]


@dataclass(frozen=True)
class LiveProjection:
    """Bounded display-only continuation authorized by two-phone evidence."""

    state: CountingState
    anchor_at: datetime | None
    live_until: datetime | None
    mutual_evidence_at: datetime | None
    provisional_seconds: int


def raw_location_expires_at(recorded_at: datetime) -> datetime:
    """Return an expiry that gives periodic cleanup time before the 24-hour ceiling."""

    if recorded_at.tzinfo is None:
        raise ValueError("recorded_at must include a timezone offset")
    return (
        recorded_at.astimezone(UTC)
        + RAW_LOCATION_RETENTION
        - PRIVACY_MAINTENANCE_INTERVAL
    )


def haversine_m(left: Point, right: Point) -> float:
    """Return great-circle distance in metres for two WGS84-like points."""

    lat1, lat2 = radians(left.latitude), radians(right.latitude)
    delta_lat = lat2 - lat1
    delta_lon = radians(right.longitude - left.longitude)
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(value))


def decide_proximity(left: Point, right: Point, threshold_m: float = 100.0) -> ProximityDecision:
    """Classify a likely-near estimate using distance and both accuracy readings."""

    measured = haversine_m(left, right)
    uncertainty = left.accuracy_m + right.accuracy_m
    minimum = max(0.0, measured - uncertainty)
    maximum = measured + uncertainty
    definite = maximum <= threshold_m
    likely = measured <= threshold_m and max(left.accuracy_m, right.accuracy_m) <= threshold_m
    together = definite or likely
    uncertain = minimum <= threshold_m < maximum
    return ProximityDecision(measured, minimum, maximum, together, uncertain)


def build_proximity_timeline(
    left: list[TimedPoint],
    right: list[TimedPoint],
    threshold_m: float = 100.0,
    *,
    clip_start: datetime | None = None,
    clip_end: datetime | None = None,
) -> ProximityTimeline:
    """Evaluate every observation without discarding faster-stream evidence."""

    events = _group_events(_deduplicate(left), _deduplicate(right))
    anchors: list[EvidenceAnchor] = []
    latest_left: TimedPoint | None = None
    latest_right: TimedPoint | None = None
    for recorded_at, new_left, new_right in events:
        latest_left = new_left or latest_left
        latest_right = new_right or latest_right
        anchors.append(_anchor(recorded_at, latest_left, latest_right, threshold_m))
    estimates: dict[datetime, MinuteEstimate] = {}
    for previous, current in pairwise(anchors):
        _add_nearby_interval(estimates, previous, current, clip_start, clip_end)
    return ProximityTimeline(
        tuple(anchors), tuple(estimates[key] for key in sorted(estimates))
    )


def estimate_nearby_minutes(
    left: list[TimedPoint],
    right: list[TimedPoint],
    threshold_m: float = 100.0,
) -> list[MinuteEstimate]:
    """Return deterministic minute estimates from chronological two-stream evidence."""

    return list(build_proximity_timeline(left, right, threshold_m).estimates)


def live_projection(
    timeline: ProximityTimeline, now: datetime, *, sharing_enabled: bool
) -> LiveProjection:
    """Authorize a short projection only after two consecutive nearby states."""

    if not timeline.anchors:
        state: CountingState = (
            "waiting_for_partner" if sharing_enabled else "sharing_disabled"
        )
        return LiveProjection(state, None, None, None, 0)
    current = timeline.anchors[-1]
    if current.left is None or current.right is None:
        state = "waiting_for_partner" if sharing_enabled else "sharing_disabled"
        return LiveProjection(state, None, None, None, 0)
    mutual_at = min(current.left.recorded_at, current.right.recorded_at).astimezone(UTC)
    if not sharing_enabled:
        return LiveProjection("sharing_disabled", None, None, mutual_at, 0)
    live_until = mutual_at + MAX_MUTUAL_EVIDENCE_AGE
    if current.state == "stale" or live_until <= now:
        return LiveProjection("stale", None, None, mutual_at, 0)
    if current.state != "nearby":
        return LiveProjection(current.state, None, None, mutual_at, 0)
    previous = timeline.anchors[-2] if len(timeline.anchors) > 1 else None
    confirmed = (
        previous is not None
        and previous.state == "nearby"
        and current.recorded_at - previous.recorded_at <= MAX_COUNTED_INTERVAL
    )
    if not confirmed or current.recorded_at > now:
        return LiveProjection("confirming", None, None, mutual_at, 0)
    projected_until = min(now, live_until)
    provisional = max(0, int((projected_until - current.recorded_at).total_seconds()))
    return LiveProjection(
        "nearby", current.recorded_at, live_until, mutual_at, provisional
    )


def _deduplicate(samples: list[TimedPoint]) -> list[TimedPoint]:
    """Choose one stable occurrence of each retry-safe sample ID."""

    unique: dict[str, TimedPoint] = {}
    for item in sorted(samples, key=lambda value: (value.recorded_at, value.sample_id)):
        unique.setdefault(item.sample_id, item)
    return sorted(unique.values(), key=lambda value: (value.recorded_at, value.sample_id))


def _group_events(
    left: list[TimedPoint], right: list[TimedPoint]
) -> list[tuple[datetime, TimedPoint | None, TimedPoint | None]]:
    """Group both streams so equal timestamps are classified atomically."""

    grouped: dict[datetime, tuple[list[TimedPoint], list[TimedPoint]]] = {}
    for side, samples in enumerate((left, right)):
        for sample in samples:
            instant = sample.recorded_at.astimezone(UTC)
            values = grouped.setdefault(instant, ([], []))
            values[side].append(sample)
    return [
        (instant, _best(values[0]), _best(values[1]))
        for instant, values in sorted(grouped.items())
    ]


def _best(samples: list[TimedPoint]) -> TimedPoint | None:
    """Choose the most accurate stable sample when one phone reports simultaneously."""

    if not samples:
        return None
    return min(samples, key=lambda value: (value.point.accuracy_m, value.sample_id))


def _anchor(
    recorded_at: datetime,
    left: TimedPoint | None,
    right: TimedPoint | None,
    threshold_m: float,
) -> EvidenceAnchor:
    """Classify the newest two-person evidence at one observation instant."""

    if left is None or right is None:
        return EvidenceAnchor(recorded_at, "waiting_for_partner", None, left, right)
    skew = abs(left.recorded_at - right.recorded_at)
    older_age = recorded_at - min(left.recorded_at, right.recorded_at)
    if skew > MAX_SAMPLE_SKEW or older_age > MAX_MUTUAL_EVIDENCE_AGE:
        return EvidenceAnchor(recorded_at, "stale", None, left, right)
    decision = decide_proximity(left.point, right.point, threshold_m)
    if decision.together:
        state: EvidenceState = "nearby"
    elif decision.minimum_distance_m > threshold_m:
        state = "apart"
    else:
        state = "poor_accuracy"
    return EvidenceAnchor(recorded_at, state, decision.measured_distance_m, left, right)


def _add_nearby_interval(
    estimates: dict[datetime, MinuteEstimate],
    previous: EvidenceAnchor,
    current: EvidenceAnchor,
    clip_start: datetime | None,
    clip_end: datetime | None,
) -> None:
    """Count only a bounded interval whose two chronological states are nearby."""

    if previous.state != "nearby" or current.state != "nearby":
        return
    if current.recorded_at <= previous.recorded_at:
        return
    if current.recorded_at - previous.recorded_at > MAX_COUNTED_INTERVAL:
        return
    start = max(previous.recorded_at, clip_start) if clip_start else previous.recorded_at
    end = min(current.recorded_at, clip_end) if clip_end else current.recorded_at
    if end <= start:
        return
    distance = max(
        previous.measured_distance_m or 0.0, current.measured_distance_m or 0.0
    )
    _split_minutes(estimates, start, end, distance)


def _split_minutes(
    estimates: dict[datetime, MinuteEstimate],
    start: datetime,
    end: datetime,
    distance: float,
) -> None:
    """Split an interval without inflating fractional fragments."""

    cursor = start
    while cursor < end:
        minute = cursor.replace(second=0, microsecond=0)
        segment_end = min(end, minute + timedelta(minutes=1))
        seconds = int((segment_end - cursor).total_seconds())
        if seconds > 0:
            existing = estimates.get(minute)
            total = min(60, seconds + (existing.duration_seconds if existing else 0))
            estimates[minute] = MinuteEstimate(minute, total, distance)
        cursor = segment_end
