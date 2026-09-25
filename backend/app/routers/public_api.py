from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.api_key_auth import get_current_api_user
from app.auth.project_permissions import (
    lock_project_for_write,
    lock_task_for_write,
    visible_project_ids,
)
from app.config import Settings, get_settings
from app.database import get_db
from app.models.project import Project
from app.models.project_member import ProjectRole
from app.models.task import Task
from app.models.user import User
from app.schemas.common import SimpleSuccessResponse, SuccessEnvelope
from app.schemas.project import ProjectResponse
from app.schemas.task import PublicTaskCreate, PublicTaskUpdate, TaskSummary
from app.services.uploads import remove_files, task_files
from app.utils.rate_limiter import ApiKeyRateLimiter


rate_limiter = ApiKeyRateLimiter()


def _rate_limit(
    x_api_key: Annotated[
        str,
        Header(
            alias="X-API-Key",
            description="API key used to authenticate and rate limit the request.",
        ),
    ],
) -> None:
    rate_limiter.check(x_api_key)


router = APIRouter(
    prefix="/api/v1/public",
    tags=["Public API"],
    dependencies=[Depends(_rate_limit)],
)

DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedApiUser = Annotated[User, Depends(get_current_api_user)]
ApplicationSettings = Annotated[Settings, Depends(get_settings)]

AUTH_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid API key."},
    status.HTTP_403_FORBIDDEN: {"description": "Account is banned."},
    status.HTTP_429_TOO_MANY_REQUESTS: {"description": "API rate limit exceeded."},
}
WRITE_RESPONSES = {
    **AUTH_RESPONSES,
    status.HTTP_403_FORBIDDEN: {"description": "Account is banned or project access is read-only."},
    status.HTTP_404_NOT_FOUND: {"description": "Resource not found or not visible."},
}


@router.get(
    "/tasks",
    summary="List accessible tasks",
    description=(
        "Return tasks from projects where the API-key user is a member. "
        "Project viewers are allowed to read tasks."
    ),
    responses=AUTH_RESPONSES,
)
def list_public_tasks(db: DatabaseSession, current_user: AuthenticatedApiUser) -> SuccessEnvelope:
    tasks = db.scalars(
        select(Task)
        .where(Task.project_id.in_(visible_project_ids(current_user.id)))
        .order_by(Task.created_at.desc(), Task.id.desc())
    ).all()
    return SuccessEnvelope(data={"tasks": [TaskSummary.model_validate(task) for task in tasks]})


@router.post(
    "/tasks",
    summary="Create a task",
    description=(
        "Create a task in an accessible project. Project owners and members with "
        "the owner or editor role may create tasks."
    ),
    responses=WRITE_RESPONSES,
)
def create_public_task(
    payload: PublicTaskCreate,
    db: DatabaseSession,
    current_user: AuthenticatedApiUser,
) -> SuccessEnvelope:
    project = lock_project_for_write(
        db, payload.project_id, current_user.id, ProjectRole.OWNER, ProjectRole.EDITOR,
    )
    task = Task(project_id=project.id, title=payload.title)
    db.add(task)
    db.commit()
    db.refresh(task)
    return SuccessEnvelope(data={"task": TaskSummary.model_validate(task)})


@router.put(
    "/tasks/{task_id}",
    summary="Update a task status",
    description=(
        "Update the status of an accessible task. Only project owners and members "
        "with the owner or editor role may modify it."
    ),
    responses=WRITE_RESPONSES,
)
def update_public_task(
    task_id: UUID,
    payload: PublicTaskUpdate,
    db: DatabaseSession,
    current_user: AuthenticatedApiUser,
) -> SuccessEnvelope:
    task = lock_task_for_write(db, task_id, current_user.id, ProjectRole.OWNER, ProjectRole.EDITOR)
    if payload.status is not None:
        task.status = payload.status
        db.commit()
        db.refresh(task)
    return SuccessEnvelope(data={"task": TaskSummary.model_validate(task)})


@router.delete(
    "/tasks/{task_id}",
    summary="Delete a task",
    description=(
        "Delete an accessible task together with its attachments, banner and "
        "comments. Only project owners may delete it."
    ),
    responses={
        **WRITE_RESPONSES,
        status.HTTP_403_FORBIDDEN: {"description": "Account is banned or not the project owner."},
    },
)
def delete_public_task(
    task_id: UUID,
    db: DatabaseSession,
    current_user: AuthenticatedApiUser,
    settings: ApplicationSettings,
) -> SimpleSuccessResponse:
    task = lock_task_for_write(
        db, task_id, current_user.id, ProjectRole.OWNER,
        forbidden_detail="Only the project owner can delete tasks",
    )
    files = task_files(db, settings, Task.id == task.id)
    db.delete(task)
    db.commit()
    remove_files(files)
    return SimpleSuccessResponse()


@router.get(
    "/projects",
    summary="List accessible projects",
    description="Return projects where the API-key user is a member.",
    responses=AUTH_RESPONSES,
)
def list_public_projects(db: DatabaseSession, current_user: AuthenticatedApiUser) -> SuccessEnvelope:
    projects = db.scalars(
        select(Project)
        .where(Project.id.in_(visible_project_ids(current_user.id)))
        .order_by(Project.created_at.desc(), Project.id.desc())
    ).all()
    return SuccessEnvelope(
        data={"projects": [ProjectResponse.model_validate(project) for project in projects]}
    )
