"""Private, coordinate-free schemas for together-time reliability surfaces."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field

from .schemas import StrictModel, StrictText


class TogetherDaySegment(StrictModel):
    """One coordinate-free minute segment for the daily timeline."""

    starts_at: datetime
    ends_at: datetime
    evidence_state: Literal[
        "observed", "bridged", "mixed", "unverified", "apart", "poor_accuracy"
    ]
    observed_seconds: int = Field(ge=0, le=60)
    bridged_seconds: int = Field(ge=0, le=60)
    unverified_seconds: int = Field(ge=0, le=60)
    apart_seconds: int = Field(ge=0, le=60)
    poor_accuracy_seconds: int = Field(ge=0, le=60)


class TogetherDayDetails(StrictModel):
    """One shared-home day without raw coordinates."""

    day: date
    timezone: str
    day_length_seconds: int
    segments: list[TogetherDaySegment]


class TogetherDeviceHealthUpdate(StrictModel):
    """Opt-in, content-free installation health supplied by its owner."""

    device_model: Annotated[StrictText, Field(min_length=1, max_length=80)]
    battery_percent: int = Field(ge=0, le=100)
    charging: bool
    network_transport: Literal["wifi", "cellular", "ethernet", "other", "offline"]
    background_location: bool
    battery_unrestricted: bool
    tracking_notification: bool
    upload_state: Literal["working", "waiting", "error"]
    queue_size: int = Field(ge=0, le=1000)


class TogetherDeviceHealthView(StrictModel):
    """An opted-in snapshot that omits its private installation identifier."""

    device_model: str
    battery_percent: int
    charging: bool
    network_transport: Literal["wifi", "cellular", "ethernet", "other", "offline"]
    background_location: bool
    battery_unrestricted: bool
    tracking_notification: bool
    upload_state: Literal["working", "waiting", "error"]
    queue_size: int
    updated_at: datetime
    last_location_at: datetime | None


class TogetherDeviceHealthResponse(StrictModel):
    """Latest current-couple snapshots grouped without stable device addresses."""

    mine: list[TogetherDeviceHealthView]
    partner: list[TogetherDeviceHealthView]
