"""
Schémas Pydantic pour l'API Tasks — cf 00-contrat-commun.md section 2
"Projects & Tasks — Owner : B".

Même logique que schemas/project.py : *Create/*Update = ce qu'un client peut
envoyer, *Response = ce que l'API renvoie.
"""

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskStatus
from app.schemas.project import ProjectMemberResponse, ProjectResponse


# ---------------------------------------------------------------------------
# Task — requêtes entrantes
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    """Body attendu pour POST /api/projects/{id}/tasks.

    `project_id` n'apparaît pas ici : il vient de l'URL (`{id}`), pas du body
    — sinon un client pourrait créer une tâche dans un projet où il n'a même
    pas accès en écrivant un autre `project_id` dans le JSON.

    Même remarque que pour `ProjectCreate` : le contrat liste `description`
    sans `?`, mais la colonne est nullable en DB → traitée comme optionnelle
    ici, à confirmer avec l'équipe.
    """

    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[date] = None


class TaskUpdate(BaseModel):
    """Body attendu pour PUT /api/tasks/{id}. Tous les champs sont optionnels :
    seuls ceux fournis par le client seront mis à jour côté routeur."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    status: Optional[TaskStatus] = None
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[date] = None


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
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Réponse de GET /api/projects/{id}/tasks → `{tasks: [...], total: N}`.

    `total` = nombre total de tâches correspondant au filtre (avant pagination),
    pas `len(tasks)` — nécessaire pour que le frontend de D affiche une
    pagination correcte. Les query params `?status=&page=` eux-mêmes ne sont
    pas un schéma ici : ils seront déclarés directement dans la signature de
    la route via `Query(...)`, pas dans un BaseModel.
    """

    tasks: list[TaskResponse]
    total: int


# ---------------------------------------------------------------------------
# GET /api/projects/{id} -> {project, members, tasks}
# ---------------------------------------------------------------------------


class ProjectDetailResponse(BaseModel):
    """Réponse complète de GET /api/projects/{id}.

    Défini ici (et pas dans schemas/project.py) parce qu'il dépend de
    `TaskResponse` : task.py peut importer project.py sans problème, l'inverse
    aurait créé un import circulaire (voir le commentaire laissé dans
    schemas/project.py).
    """

    project: ProjectResponse
    members: list[ProjectMemberResponse]
    tasks: list[TaskResponse]
