"""Pure tests for bounded, two-phone together-time projection."""

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from little_orbit_api.domain.location import (
    Point,
    TimedPoint,
    build_proximity_timeline,
    live_projection,
)
from little_orbit_api.routes import together_time_legacy


def test_projection_advances_only_to_older_sample_deadline() -> None:
    start = datetime(2026, 9, 16, 12, tzinfo=UTC)
    timeline = build_proximity_timeline(
        [_sample("a0", start), _sample("a2", start + timedelta(minutes=2))],
        [_sample("b0", start), _sample("b2", start + timedelta(minutes=2))],
    )

    active = live_projection(
        timeline, start + timedelta(minutes=4, seconds=12), sharing_enabled=True
    )
    expired = live_projection(
        timeline, start + timedelta(minutes=7), sharing_enabled=True
    )

    assert active.state == "nearby"
    assert active.anchor_at == start + timedelta(minutes=2)
    assert active.live_until == start + timedelta(minutes=7)
    assert active.provisional_seconds == 132
    assert expired.state == "stale"
    assert expired.provisional_seconds == 0


def test_one_phone_cannot_start_or_renew_projection() -> None:
    start = datetime(2026, 9, 16, 12, tzinfo=UTC)
    timeline = build_proximity_timeline(
        [_sample("a0", start), _sample("a2", start + timedelta(minutes=2))], []
    )

    result = live_projection(timeline, start + timedelta(minutes=2), sharing_enabled=True)

    assert result.state == "waiting_for_partner"
    assert result.live_until is None


def test_first_mutual_observation_requires_confirmation() -> None:
    start = datetime(2026, 9, 16, 12, tzinfo=UTC)
    timeline = build_proximity_timeline(
        [_sample("a0", start)], [_sample("b0", start)]
    )

    result = live_projection(timeline, start + timedelta(seconds=20), sharing_enabled=True)

    assert result.state == "confirming"
    assert result.provisional_seconds == 0


def test_consent_removal_overrides_fresh_evidence() -> None:
    start = datetime(2026, 9, 16, 12, tzinfo=UTC)
    timeline = build_proximity_timeline(
        [_sample("a0", start), _sample("a1", start + timedelta(minutes=1))],
        [_sample("b0", start), _sample("b1", start + timedelta(minutes=1))],
    )

    result = live_projection(timeline, start + timedelta(minutes=2), sharing_enabled=False)

    assert result.state == "sharing_disabled"
    assert result.provisional_seconds == 0
    assert result.mutual_evidence_at == start + timedelta(minutes=1)


def test_legacy_together_time_writers_are_terminally_retired() -> None:
    app = FastAPI()
    app.include_router(together_time_legacy.router)

    with TestClient(app) as client:
        response = client.post("/v2/together-time/locations", json={})

    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "route_retired"


def _sample(sample_id: str, recorded_at: datetime) -> TimedPoint:
    return TimedPoint(sample_id, recorded_at, Point(45, -122, 5))
