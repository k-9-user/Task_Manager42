"""
Router FastAPI pour les tâches — cf 00-contrat-commun.md section 2
"Projects & Tasks — Owner : B".

Mêmes dépendances non livrées que routers/projects.py (cf en-tête de ce
fichier) : `app.database.get_db`, `app.auth.dependencies.get_current_user`.

Les routes sont réparties sur deux préfixes différents dans le contrat
(`/api/projects/{id}/tasks` et `/api/tasks/{id}`), donc ce router ne
déclare pas de `prefix` global comme `routers/projects.py` : chaque route
écrit son chemin complet.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task, TaskStatus
from app.routers.projects import _get_membership_or_404, _require_role
from app.schemas.common import SimpleSuccessResponse, SuccessEnvelope
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate

router = APIRouter(tags=["tasks"])

# Contrat : `GET /api/projects/{id}/tasks` ne précise qu'un `?page=`, pas de
# `?limit=` (contrairement à `GET /api/search/tasks` qui a les deux). On fixe
# donc une taille de page constante ici — à discuter si l'équipe veut plutôt
# un `?limit=` réglable, comme sur les autres routes paginées.
PAGE_SIZE = 20


def _assert_valid_assignee(db: Session, project_id: uuid.UUID, assignee_id: uuid.UUID) -> None:
    """Refuse d'assigner une tâche à quelqu'un qui n'est pas membre du projet.

    Décision prise pour combler un point non précisé par le contrat (cf
    SUIVI-PERSONNE-B.md) : assigner une tâche à un non-membre n'aurait pas de
    sens (il ne pourrait même pas voir le projet). À valider en équipe.
    """

    is_member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == assignee_id)
        .first()
    )
    if is_member is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'utilisateur assigné doit être membre du projet",
        )


# ---------------------------------------------------------------------------
# GET /api/projects/{id}/tasks
# ---------------------------------------------------------------------------


@router.get(
    "/api/projects/{project_id}/tasks", response_model=SuccessEnvelope[TaskListResponse]
)
def list_tasks(
    project_id: uuid.UUID,
    status_filter: Optional[TaskStatus] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """N'importe quel membre (owner/editor/viewer) peut lister les tâches —
    lecture seule, pas de restriction de rôle ici."""

    _get_membership_or_404(db, project_id, current_user.id)

    query = db.query(Task).filter(Task.project_id == project_id)
    if status_filter is not None:
        query = query.filter(Task.status == status_filter)

    total = query.count()
    tasks = (
        query.order_by(Task.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )

    return SuccessEnvelope(
        data=TaskListResponse(
            tasks=[TaskResponse.model_validate(t) for t in tasks], total=total
        )
    )


# ---------------------------------------------------------------------------
# POST /api/projects/{id}/tasks
# ---------------------------------------------------------------------------


@router.post(
    "/api/projects/{project_id}/tasks",
    response_model=SuccessEnvelope[TaskResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    project_id: uuid.UUID,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Seuls owner et editor peuvent créer une tâche — un viewer est en
    lecture seule (cf 02-fiche-personne-B.md, "un viewer ne peut pas modifier
    une tâche")."""

    membership = _get_membership_or_404(db, project_id, current_user.id)
    _require_role(membership, ProjectRole.OWNER, ProjectRole.EDITOR)

    if payload.assignee_id is not None:
        _assert_valid_assignee(db, project_id, payload.assignee_id)

    task = Task(
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        assignee_id=payload.assignee_id,
        due_date=payload.due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return SuccessEnvelope(data=TaskResponse.model_validate(task))


# ---------------------------------------------------------------------------
# PUT /api/tasks/{id}
# ---------------------------------------------------------------------------


@router.put("/api/tasks/{task_id}", response_model=SuccessEnvelope[TaskResponse])
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable")

    membership = _get_membership_or_404(db, task.project_id, current_user.id)
    _require_role(membership, ProjectRole.OWNER, ProjectRole.EDITOR)

    updates = payload.model_dump(exclude_unset=True)

    if updates.get("assignee_id") is not None:
        _assert_valid_assignee(db, task.project_id, updates["assignee_id"])

    for field, value in updates.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)

    return SuccessEnvelope(data=TaskResponse.model_validate(task))


# ---------------------------------------------------------------------------
# DELETE /api/tasks/{id}
# ---------------------------------------------------------------------------


@router.delete("/api/tasks/{task_id}", response_model=SimpleSuccessResponse)
def delete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable")

    membership = _get_membership_or_404(db, task.project_id, current_user.id)
    _require_role(membership, ProjectRole.OWNER, ProjectRole.EDITOR)

    db.delete(task)
    db.commit()

    return SimpleSuccessResponse()
