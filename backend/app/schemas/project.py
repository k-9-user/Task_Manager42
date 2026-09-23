import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.project_member import ProjectRole
from app.schemas.common import StrictRequest


# ---------------------------------------------------------------------------
# Project — requêtes entrantes
# ---------------------------------------------------------------------------


class ProjectCreate(StrictRequest):
    """Body attendu pour POST /api/projects."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)


class ProjectUpdate(StrictRequest):
    """Body attendu pour PUT /api/projects/{id}."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)


# ---------------------------------------------------------------------------
# Project — réponses sortantes
# ---------------------------------------------------------------------------


class ProjectResponse(BaseModel):
    """Représentation d'un projet renvoyée par l'API (clé "project" dans les réponses)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str] = None
    owner_id: uuid.UUID
    created_at: datetime


class ProjectListResponse(BaseModel):
    """Réponse de GET /api/projects → `{"success": true, "data": {"projects": [...]}}`."""

    projects: list[ProjectResponse]


class ProjectData(BaseModel):
    project: ProjectResponse


# ---------------------------------------------------------------------------
# Project members
# ---------------------------------------------------------------------------


class ProjectMemberCreate(StrictRequest):
    """Body attendu pour POST /api/projects/{id}/members."""

    user_id: uuid.UUID
    role: ProjectRole


class ProjectMemberResponse(BaseModel):
    """Représentation d'un membre de projet renvoyée par l'API (clé "member")."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    role: ProjectRole
    username: str
    email: EmailStr


class ProjectMemberData(BaseModel):
    member: ProjectMemberResponse


class ProjectMemberListResponse(BaseModel):
    members: list[ProjectMemberResponse]
