from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class StrictRequest(BaseModel):
    """Reject fields that are not part of the documented request body."""

    model_config = ConfigDict(extra="forbid")


class SuccessEnvelope(BaseModel, Generic[T]):
    success: Literal[True] = True
    data: T


class SimpleSuccessResponse(BaseModel):
    """`{"success": true, "data": {}}`, for routes such as deletions that return nothing."""

    success: Literal[True] = True
    data: dict[str, object] = Field(default_factory=dict)
