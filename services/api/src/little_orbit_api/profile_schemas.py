"""Authenticated profile identity response schemas."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProfileModel(BaseModel):
    """Strict base for profile responses."""

    model_config = ConfigDict(extra="forbid")


class ProfilePhotoMetadata(ProfileModel):
    """Cache-safe metadata for one private normalized profile image."""

    revision: int = Field(ge=1)
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    updated_at: datetime


class OrbitProfilePerson(ProfileModel):
    """Display identity exposed only to its owner or current partner."""

    display_name: Annotated[str, Field(min_length=1, max_length=80)]
    photo: ProfilePhotoMetadata | None
    name_revision: int = Field(default=0, ge=0)
    partner_assigned: bool = False


class PartnerNameMutation(ProfileModel):
    """Retry-safe partner-name assignment."""

    operation_id: UUID
    expected_revision: int = Field(ge=0)
    display_name: Annotated[str, Field(min_length=1, max_length=80)]


class PartnerNameReset(ProfileModel):
    """Retry-safe reset to the privacy-safe account-name fallback."""

    operation_id: UUID
    expected_revision: int = Field(ge=0)


class PartnerNameState(ProfileModel):
    """Visible result of one partner-controlled relationship name."""

    display_name: Annotated[str, Field(min_length=1, max_length=80)]
    assigned_name: Annotated[str, Field(min_length=1, max_length=40)] | None
    revision: int = Field(ge=1)
    partner_assigned: bool
    updated_at: datetime


class OrbitProfileResponse(ProfileModel):
    """The authenticated account and optional current partner display identities."""

    me: OrbitProfilePerson
    partner: OrbitProfilePerson | None
