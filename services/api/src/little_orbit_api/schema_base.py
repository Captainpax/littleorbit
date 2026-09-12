"""Shared strict schema primitives without feature-level dependencies."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

StrictText = Annotated[str, StringConstraints(strip_whitespace=True)]


class StrictModel(BaseModel):
    """Base network model that rejects undeclared fields."""

    model_config = ConfigDict(extra="forbid")
