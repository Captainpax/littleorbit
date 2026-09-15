"""Strict request and response contracts for administrator authentication."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import EmailStr, Field, model_validator

from .schema_base import StrictModel


class AdminEnrollmentStart(StrictModel):
    """Password plus the current factor when replacing enabled administrator MFA."""

    password: Annotated[str, Field(min_length=1, max_length=256)]
    current_totp_code: Annotated[
        str | None, Field(default=None, pattern=r"^[0-9]{6}$")
    ]
    current_recovery_code: Annotated[
        str | None, Field(default=None, min_length=13, max_length=32)
    ]

    @model_validator(mode="after")
    def one_current_factor(self) -> "AdminEnrollmentStart":
        """Reject ambiguous proofs without requiring one for first enrollment."""

        if self.current_totp_code and self.current_recovery_code:
            raise ValueError("provide one current MFA proof")
        return self


class AdminEnrollmentChallenge(StrictModel):
    """Temporary authenticator enrollment material."""

    otpauth_uri: str
    qr_svg_data_url: str


class AdminEnrollmentConfirm(StrictModel):
    """First authenticator code that proves enrollment succeeded."""

    code: Annotated[str, Field(pattern=r"^[0-9]{6}$")]


class AdminSessionRequest(StrictModel):
    """Password plus TOTP or a one-time recovery code."""

    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=256)]
    totp_code: Annotated[str | None, Field(default=None, pattern=r"^[0-9]{6}$")]
    recovery_code: Annotated[str | None, Field(default=None, min_length=13, max_length=32)]


class AdminSessionResponse(StrictModel):
    """MFA-verified owner session and one-time enrollment recovery codes."""

    access_token: str
    expires_at: datetime
    account_id: UUID
    recovery_codes: list[str] = Field(default_factory=list)
