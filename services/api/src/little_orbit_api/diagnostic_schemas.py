"""Strict, content-free client contract for opt-in Android crash diagnostics."""

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .schema_base import StrictModel

MAX_REPORT_BYTES = 65_536
EXCEPTION_CLASS = re.compile(
    r"^(?:java|android|androidx|com\.littleorbit)\.[A-Za-z_$][A-Za-z0-9_.$]{0,150}$"
)
APP_CLASS = re.compile(r"^com\.littleorbit\.[A-Za-z_$][A-Za-z0-9_.$]{0,140}$")
METHOD = re.compile(r"^[A-Za-z_$<>][A-Za-z0-9_$<>]{0,119}$")


class CrashFrame(StrictModel):
    """One allowlisted Little Orbit code location without paths or runtime values."""

    class_name: str = Field(min_length=1, max_length=160)
    method_name: str = Field(min_length=1, max_length=120)
    line_number: int | None = Field(default=None, ge=1, le=1_000_000)

    @field_validator("class_name")
    @classmethod
    def app_owned_class(cls, value: str) -> str:
        """Accept only classes built into a Little Orbit APK."""

        if not APP_CLASS.fullmatch(value):
            raise ValueError("diagnostic frames must be app-owned")
        return value

    @field_validator("method_name")
    @classmethod
    def java_method(cls, value: str) -> str:
        """Reject free-form method text, paths, and values."""

        if not METHOD.fullmatch(value):
            raise ValueError("diagnostic method is invalid")
        return value


class CrashReportRequest(StrictModel):
    """Bounded identifiers produced only after explicit diagnostic opt-in."""

    consent: Literal[True]
    installation_id: UUID
    app_version_code: int = Field(ge=1, le=2_147_483_647)
    app_version_name: str = Field(pattern=r"^[0-9A-Za-z._-]{1,40}$")
    exception_chain: list[str] = Field(min_length=1, max_length=8)
    frames: list[CrashFrame] = Field(min_length=1, max_length=64)
    occurred_at: datetime

    @field_validator("exception_chain")
    @classmethod
    def known_exception_classes(cls, values: list[str]) -> list[str]:
        """Allow platform and app class identifiers, never exception messages."""

        if any(not EXCEPTION_CLASS.fullmatch(value) for value in values):
            raise ValueError("diagnostic exception class is invalid")
        return values

    @model_validator(mode="after")
    def bounded_encoded_size(self) -> "CrashReportRequest":
        """Keep the structured report below the documented wire ceiling."""

        text = [self.app_version_name, *self.exception_chain]
        for frame in self.frames:
            text.extend((frame.class_name, frame.method_name, str(frame.line_number or 0)))
        if sum(len(value.encode("utf-8")) for value in text) > MAX_REPORT_BYTES:
            raise ValueError("diagnostic report exceeds 64 KiB")
        return self
