"""Privacy and retention tests for opt-in crash diagnostics."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from little_orbit_api.diagnostic_schemas import CrashFrame, CrashReportRequest
from little_orbit_api.diagnostics import (
    canonical_diagnostic,
    diagnostic_fingerprint,
    retention_deadlines,
)


def frame(line: int = 12) -> CrashFrame:
    """Build one app-owned frame without runtime content."""

    return CrashFrame(
        class_name="com.littleorbit.mobile.MainActivity",
        method_name="renderHome",
        line_number=line,
    )


def test_diagnostic_contract_has_no_free_form_runtime_content() -> None:
    report = CrashReportRequest(
        consent=True,
        installation_id=uuid4(),
        app_version_code=19,
        app_version_name="1.0.0-rc.14",
        exception_chain=["java.lang.IllegalStateException"],
        frames=[frame()],
        occurred_at=datetime.now(UTC),
    )

    chain, frames = canonical_diagnostic(report.exception_chain, report.frames)
    assert "IllegalStateException" in chain
    assert "renderHome" in frames
    assert "message" not in report.model_dump()
    assert "stack_trace" not in report.model_dump()


@pytest.mark.parametrize(
    ("class_name", "method_name"),
    [
        ("com.partner.private.Note", "render"),
        ("com.littleorbit.mobile.Home", "render /data/user/0/private"),
    ],
)
def test_diagnostic_frame_rejects_external_or_free_form_values(
    class_name: str, method_name: str
) -> None:
    with pytest.raises(ValidationError):
        CrashFrame(class_name=class_name, method_name=method_name, line_number=1)


def test_diagnostic_contract_rejects_arbitrary_exception_text() -> None:
    with pytest.raises(ValidationError):
        CrashReportRequest(
            consent=True,
            installation_id=uuid4(),
            app_version_code=19,
            app_version_name="1.0.0-rc.14",
            exception_chain=["password=secret"],
            frames=[frame()],
            occurred_at=datetime.now(UTC),
        )


def test_diagnostic_fingerprint_changes_only_with_code_location() -> None:
    chain = ["java.lang.IllegalStateException"]
    assert diagnostic_fingerprint(chain, [frame(12)]) == diagnostic_fingerprint(
        chain, [frame(12)]
    )
    assert diagnostic_fingerprint(chain, [frame(12)]) != diagnostic_fingerprint(
        chain, [frame(13)]
    )


def test_diagnostic_contract_rejects_more_than_64_frames() -> None:
    with pytest.raises(ValidationError):
        CrashReportRequest(
            consent=True,
            installation_id=uuid4(),
            app_version_code=19,
            app_version_name="1.0.0-rc.14",
            exception_chain=["java.lang.IllegalStateException"],
            frames=[frame(index + 1) for index in range(65)],
            occurred_at=datetime.now(UTC),
        )


def test_diagnostic_retention_is_exactly_30_and_90_days() -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    raw, aggregate = retention_deadlines(now)

    assert (raw - now).days == 30
    assert (aggregate - now).days == 90
