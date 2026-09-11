"""Pure distance and proximity decisions for together-time estimates."""

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_M = 6_371_000.0


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
