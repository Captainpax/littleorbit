"""Pure distance and proximity decisions for together-time estimates."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6_371_000.0
PAIR_WINDOW = timedelta(minutes=10)
MAX_CONFIDENT_GAP = timedelta(minutes=20)


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
class MinuteEstimate:
    """Coordinate-free overlap within one UTC minute."""

    bucket_start: datetime
    duration_seconds: int
    estimated_distance_m: float


def haversine_m(left: Point, right: Point) -> float:
    """Return great-circle distance in metres for two WGS84-like points."""

    lat1, lat2 = radians(left.latitude), radians(right.latitude)
    delta_lat = lat2 - lat1
    delta_lon = radians(right.longitude - left.longitude)
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(value))


def decide_proximity(left: Point, right: Point, threshold_m: float = 100.0) -> ProximityDecision:
    """Classify proximity conservatively while exposing accuracy uncertainty."""

    measured = haversine_m(left, right)
    uncertainty = left.accuracy_m + right.accuracy_m
    minimum = max(0.0, measured - uncertainty)
    maximum = measured + uncertainty
    together = maximum <= threshold_m
    uncertain = minimum <= threshold_m < maximum
    return ProximityDecision(measured, minimum, maximum, together, uncertain)


def estimate_nearby_minutes(
    left: list[TimedPoint],
    right: list[TimedPoint],
    threshold_m: float = 100.0,
) -> list[MinuteEstimate]:
    """Match two sample streams and count only consecutive confident intervals."""

    pairs = _match_samples(_deduplicate(left), _deduplicate(right))
    anchors = [
        (
            max(first.recorded_at, second.recorded_at).astimezone(UTC),
            decide_proximity(first.point, second.point, threshold_m),
        )
        for first, second in pairs
    ]
    estimates: dict[datetime, MinuteEstimate] = {}
    for previous, current in pairwise(anchors):
        _add_confident_interval(estimates, previous, current)
    return [estimates[key] for key in sorted(estimates)]


def _deduplicate(samples: list[TimedPoint]) -> list[TimedPoint]:
    """Choose one stable occurrence of each retry-safe sample ID."""

    ordered = sorted(samples, key=lambda item: (item.recorded_at, item.sample_id))
    return list({item.sample_id: item for item in ordered}.values())


def _match_samples(
    left: list[TimedPoint], right: list[TimedPoint]
) -> list[tuple[TimedPoint, TimedPoint]]:
    """Greedily choose deterministic one-to-one pairs within ten minutes."""

    candidates = [
        (
            abs((first.recorded_at - second.recorded_at).total_seconds()),
            first.recorded_at,
            first.sample_id,
            second.recorded_at,
            second.sample_id,
            first,
            second,
        )
        for first in left
        for second in right
        if abs(first.recorded_at - second.recorded_at) <= PAIR_WINDOW
    ]
    used_left: set[str] = set()
    used_right: set[str] = set()
    matches: list[tuple[TimedPoint, TimedPoint]] = []
    for *_, first, second in sorted(candidates, key=lambda item: item[:5]):
        if first.sample_id in used_left or second.sample_id in used_right:
            continue
        used_left.add(first.sample_id)
        used_right.add(second.sample_id)
        matches.append((first, second))
    return sorted(matches, key=lambda pair: max(pair[0].recorded_at, pair[1].recorded_at))


def _add_confident_interval(
    estimates: dict[datetime, MinuteEstimate],
    previous: tuple[datetime, ProximityDecision],
    current: tuple[datetime, ProximityDecision],
) -> None:
    start, start_decision = previous
    end, end_decision = current
    if not start_decision.together or not end_decision.together:
        return
    if end <= start or end - start > MAX_CONFIDENT_GAP:
        return
    distance = max(start_decision.measured_distance_m, end_decision.measured_distance_m)
    cursor = start
    while cursor < end:
        minute = cursor.replace(second=0, microsecond=0)
        segment_end = min(end, minute + timedelta(minutes=1))
        seconds = max(1, int((segment_end - cursor).total_seconds()))
        existing = estimates.get(minute)
        total = min(60, seconds + (existing.duration_seconds if existing else 0))
        estimates[minute] = MinuteEstimate(minute, total, distance)
        cursor = segment_end
