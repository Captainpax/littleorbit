"""Strict contracts for the device-bound Big Orbit Android console."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import EmailStr, Field, model_validator

from .schema_base import StrictModel


class DeviceChallengeRequest(StrictModel):
    """Requests a short proof-of-possession challenge without revealing device state."""

    device_id: UUID


class DeviceChallengeResponse(StrictModel):
    """Public random challenge; secrecy is neither required nor assumed."""

    challenge_id: UUID
    challenge: str
    expires_at: datetime


class BigOrbitSessionRequest(StrictModel):
    """Password/MFA login plus enrollment or an existing device signature."""

    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=256)]
    totp_code: Annotated[str | None, Field(default=None, pattern=r"^[0-9]{6}$")]
    recovery_code: Annotated[str | None, Field(default=None, min_length=13, max_length=32)]
    enrollment_public_key: Annotated[
        str | None, Field(default=None, min_length=80, max_length=512)
    ]
    device_label: Annotated[str | None, Field(default=None, min_length=1, max_length=80)]
    device_id: UUID | None = None
    challenge_id: UUID | None = None
    challenge: Annotated[str | None, Field(default=None, min_length=24, max_length=128)]
    signature: Annotated[str | None, Field(default=None, min_length=40, max_length=256)]

    @model_validator(mode="after")
    def one_device_flow(self) -> "BigOrbitSessionRequest":
        """Require one complete enrollment or returning-device proof."""

        enrollment = self.enrollment_public_key is not None or self.device_label is not None
        returning = any(
            value is not None
            for value in (self.device_id, self.challenge_id, self.challenge, self.signature)
        )
        if enrollment == returning:
            raise ValueError("provide one complete device flow")
        if enrollment and (self.enrollment_public_key is None or self.device_label is None):
            raise ValueError("device enrollment is incomplete")
        if returning and any(
            value is None
            for value in (self.device_id, self.challenge_id, self.challenge, self.signature)
        ):
            raise ValueError("device proof is incomplete")
        if bool(self.totp_code) == bool(self.recovery_code):
            raise ValueError("provide exactly one MFA proof")
        return self


class BigOrbitSessionResponse(StrictModel):
    """Short administrator session bound to exactly one Big Orbit device."""

    access_token: str
    expires_at: datetime
    account_id: UUID
    device_id: UUID
    enrollment_required: bool
    enrollment_challenge: DeviceChallengeResponse | None = None


class DeviceEnrollmentConfirm(StrictModel):
    """Signed enrollment challenge from the newly created Keystore key."""

    challenge_id: UUID
    challenge: Annotated[str, Field(min_length=24, max_length=128)]
    signature: Annotated[str, Field(min_length=40, max_length=256)]


class DeviceEnrollmentResult(StrictModel):
    """Long-lived random credential displayed to the enrolled app only once."""

    device_id: UUID
    device_credential: str
    credential_expires_at: datetime


class DeviceSessionRequest(StrictModel):
    """Device credential plus fresh key signature for background session rotation."""

    device_id: UUID
    device_credential: Annotated[str, Field(min_length=32, max_length=160)]
    challenge_id: UUID
    challenge: Annotated[str, Field(min_length=24, max_length=128)]
    signature: Annotated[str, Field(min_length=40, max_length=256)]


class AdminDeviceView(StrictModel):
    """Safe enrolled-device metadata."""

    id: UUID
    label: str
    key_fingerprint: str
    approved_at: datetime | None
    revoked_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime


class AdminAlertView(StrictModel):
    """Content-free action-inbox item."""

    id: UUID
    kind: str
    severity: Literal["info", "warning", "critical"]
    title: str
    summary: str
    action_path: str | None
    created_at: datetime
    acknowledged: bool


class AdminAlertAck(StrictModel):
    """Idempotent per-device alert acknowledgement."""

    alert_ids: list[UUID] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_ids(self) -> "AdminAlertAck":
        if len(set(self.alert_ids)) != len(self.alert_ids):
            raise ValueError("alert IDs must be unique")
        return self


class AdminJobMutation(StrictModel):
    """Allowlisted operation; no command, SQL, path, or arbitrary arguments."""

    operation_id: UUID
    kind: Literal["learn_quizzes", "generate_quizzes", "backup", "test_restore"]
    target_week: date | None = None


class AdminJobView(StrictModel):
    """Content-free state for a typed operation request."""

    id: UUID
    kind: str
    target_week: date | None
    status: str
    result: dict[str, object]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
