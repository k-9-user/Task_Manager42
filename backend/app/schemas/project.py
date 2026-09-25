import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.project_member import ProjectRole
from app.schemas.common import StrictRequest


class ProjectCreate(StrictRequest):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)


class ProjectUpdate(StrictRequest):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    owner_id: uuid.UUID
    created_at: datetime


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]


class ProjectData(BaseModel):
    project: ProjectResponse


class ProjectMemberCreate(StrictRequest):
    user_id: uuid.UUID
    role: ProjectRole


class ProjectMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    role: ProjectRole
    username: str
    email: EmailStr
    level: int
    badge: str | None = None


class ProjectMemberData(BaseModel):
    member: ProjectMemberResponse
