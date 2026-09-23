import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import StrictRequest


class ProjectMessageCreate(StrictRequest):
    content: str = Field(..., min_length=1, max_length=2000)


class ProjectMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    author_id: uuid.UUID
    author_username: str
    content: str
    created_at: datetime


class ProjectMessageListResponse(BaseModel):
    messages: list[ProjectMessageResponse]


class ProjectMessageData(BaseModel):
    message: ProjectMessageResponse
