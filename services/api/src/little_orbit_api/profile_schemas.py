"""Authenticated profile identity response schemas."""

from datetime import datetime
from typing import Annotated

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


class OrbitProfileResponse(ProfileModel):
    """The authenticated account and optional current partner display identities."""

    me: OrbitProfilePerson
    partner: OrbitProfilePerson | None
