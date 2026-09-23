import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.task import TaskStatus
from app.schemas.common import StrictRequest
from app.schemas.project import ProjectMemberResponse, ProjectResponse


# ---------------------------------------------------------------------------
# Task — requêtes entrantes
# ---------------------------------------------------------------------------


class TaskCreate(StrictRequest):
    """Body attendu pour POST /api/projects/{id}/tasks.

    `project_id` n'apparaît pas ici : il vient de l'URL (`{id}`), pas du body
    — sinon un client pourrait créer une tâche dans un projet où il n'a même
    pas accès en écrivant un autre `project_id` dans le JSON.
    """

    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[date] = None


class TaskUpdate(StrictRequest):
    """Body attendu pour PUT /api/tasks/{id}. Tous les champs sont optionnels :
    seuls ceux fournis par le client seront mis à jour côté routeur."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    status: Optional[TaskStatus] = None
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[date] = None


class TaskImportRecord(StrictRequest):
    """Writable task fields plus metadata emitted by supported exports."""

    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus = TaskStatus.TODO
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None
    id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    project_name: str | None = Field(default=None, max_length=255)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, title: str) -> str:
        title = title.strip()
        if not title:
            raise ValueError("title must not be empty")
        return title


# ---------------------------------------------------------------------------
# Task — réponses sortantes
# ---------------------------------------------------------------------------


class TaskResponse(BaseModel):
    """Représentation d'une tâche renvoyée par l'API (clé "task" dans les réponses)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: Optional[str] = None
    status: TaskStatus
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[date] = None
    banner_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Réponse de GET /api/projects/{id}/tasks → `{tasks: [...], total: N}`.

    `total` = nombre total de tâches correspondant au filtre (avant pagination),
    pas `len(tasks)`.
    """

    tasks: list[TaskResponse]
    total: int


class TaskData(BaseModel):
    task: TaskResponse


# ---------------------------------------------------------------------------
# GET /api/projects/{id} -> {project, members, tasks}
# ---------------------------------------------------------------------------


class ProjectDetailResponse(BaseModel):
    """Réponse complète de GET /api/projects/{id} → `{project, members, tasks}`."""

    project: ProjectResponse
    members: list[ProjectMemberResponse]
    tasks: list[TaskResponse]
