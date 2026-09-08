"""
Schémas Pydantic pour l'API Projects — cf 00-contrat-commun.md section 2
"Projects & Tasks — Owner : B".

Un schéma Pydantic n'est PAS un modèle SQLAlchemy : il ne décrit pas une table,
il décrit la forme d'un JSON qui entre ou sort de l'API. On en a deux familles :
- les schémas "*Create" / "*Update" : ce qu'un client a le DROIT d'envoyer dans
  le body d'une requête (ex: un client ne doit jamais pouvoir fixer lui-même
  l'id ou owner_id d'un projet, donc ces champs n'apparaissent pas ici).
- les schémas "*Response" : ce que l'API renvoie. Ils reprennent les champs du
  modèle SQLAlchemy correspondant, convertis en JSON.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.project_member import ProjectRole


# ---------------------------------------------------------------------------
# Project — requêtes entrantes
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    """Body attendu pour POST /api/projects.

    NB : le contrat commun liste `{name, description}` sans `?` sur
    `description`, mais la colonne `projects.description` est nullable en DB.
    On la traite ici comme optionnelle pour rester cohérent avec le schéma DB
    — à confirmer avec l'équipe et à corriger dans le contrat si besoin.
    """

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)


class ProjectUpdate(BaseModel):
    """Body attendu pour PUT /api/projects/{id}.

    Tous les champs sont optionnels : un client ne renvoie que ce qu'il veut
    changer. Le routeur ne mettra à jour que les champs réellement fournis
    (voir `model_dump(exclude_unset=True)` au moment d'écrire routers/projects.py).
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)


# ---------------------------------------------------------------------------
# Project — réponses sortantes
# ---------------------------------------------------------------------------


class ProjectResponse(BaseModel):
    """Représentation d'un projet renvoyée par l'API (clé "project" dans les réponses).

    `model_config = ConfigDict(from_attributes=True)` est ce qui permet de faire
    `ProjectResponse.model_validate(project_sqlalchemy_instance)` directement,
    sans reconstruire un dict à la main : Pydantic va lire les attributs
    `.id`, `.name`, etc. sur l'objet SQLAlchemy.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str] = None
    owner_id: uuid.UUID
    created_at: datetime


class ProjectListResponse(BaseModel):
    """Réponse de GET /api/projects → `{"success": true, "data": {"projects": [...]}}`."""

    projects: list[ProjectResponse]


# ---------------------------------------------------------------------------
# Project members
# ---------------------------------------------------------------------------


class ProjectMemberCreate(BaseModel):
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


# ---------------------------------------------------------------------------
# GET /api/projects/{id} -> {project, members, tasks}
# ---------------------------------------------------------------------------
# Pas de schéma composite ici : `tasks` dépend de TaskResponse, défini dans
# schemas/task.py (prochain fichier). Pour éviter un import circulaire
# project.py <-> task.py, le routeur construira directement le dict de
# réponse à partir de ProjectResponse, ProjectMemberResponse et TaskResponse :
#
#   {"project": ProjectResponse.model_validate(project),
#    "members": [ProjectMemberResponse.model_validate(m) for m in project.members],
#    "tasks": [TaskResponse.model_validate(t) for t in project.tasks]}
