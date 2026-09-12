"""Public release-history response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReleaseHistoryItem(BaseModel):
    """Published release fields safe for public patch-note feeds."""

    model_config = ConfigDict(extra="forbid")

    version: str
    version_code: int
    github_release_url: str
    sha256: str
    minimum_android: int
    release_notes: str
    published_at: datetime
