from enum import Enum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.api_key_auth import get_current_api_user
from app.auth.project_permissions import lock_project_for_write
from app.database import get_db
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.utils.rate_limiter import ApiKeyRateLimiter


router = APIRouter(
    prefix="/api/v1/public",
    tags=["Public API"],
)
rate_limiter = ApiKeyRateLimiter()

DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedApiUser = Annotated[User, Depends(get_current_api_user)]
RawApiKey = Annotated[
    str,
    Header(
        alias="X-API-Key",
        description="API key used to authenticate and rate limit the request.",
    ),
]

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


class PublicTaskCreate(BaseModel):
    """Minimal request body for the public task creation contract."""

    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    title: str = Field(min_length=1)

    @field_validator("title")
    @classmethod
    def validate_title(cls, title: str) -> str:
        if not title.strip():
            raise ValueError("title must not be empty")
        return title


class PublicTaskUpdate(BaseModel):
    """Fields that the public API is allowed to update on a task."""

    model_config = ConfigDict(extra="forbid")

    status: TaskStatus | None = None


@router.get(
    "/tasks",
    summary="List accessible tasks",
    description=(
        "Return tasks from projects where the API-key user is a member. "
        "Project viewers are allowed to read tasks."
    ),
    responses=AUTH_RESPONSES,
)
def list_public_tasks(
    db: DatabaseSession,
    current_user: AuthenticatedApiUser,
    x_api_key: RawApiKey,
) -> dict[str, Any]:
    rate_limiter.check(x_api_key)
    tasks = db.scalars(
        select(Task)
        .join(Project, Task.project_id == Project.id)
        .where(_project_access_filter(current_user.id))
    ).all()

    return _success_response(tasks=[_serialize_task(task) for task in tasks])


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
    x_api_key: RawApiKey,
) -> dict[str, Any]:
    rate_limiter.check(x_api_key)
    project = lock_project_for_write(
        db, payload.project_id, current_user.id, ProjectRole.OWNER, ProjectRole.EDITOR,
    )

    task = Task(project_id=project.id, title=payload.title)
    db.add(task)
    db.commit()
    db.refresh(task)

    return _success_response(task=_serialize_task(task))


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
    x_api_key: RawApiKey,
) -> dict[str, Any]:
    rate_limiter.check(x_api_key)
    project_id = db.scalar(select(Task.project_id).where(Task.id == task_id))
    if project_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    lock_project_for_write(
        db, project_id, current_user.id, ProjectRole.OWNER, ProjectRole.EDITOR,
        not_found_detail="Task not found",
    )
    task = db.scalar(
        select(Task).where(Task.id == task_id).execution_options(populate_existing=True)
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if payload.status is not None:
        task.status = payload.status
        db.add(task)
        db.commit()
        db.refresh(task)

    return _success_response(task=_serialize_task(task))


@router.delete(
    "/tasks/{task_id}",
    summary="Delete a task",
    description=(
        "Delete an accessible task. Only project owners and members with the owner "
        "or editor role may delete it."
    ),
    responses=WRITE_RESPONSES,
)
def delete_public_task(
    task_id: UUID,
    db: DatabaseSession,
    current_user: AuthenticatedApiUser,
    x_api_key: RawApiKey,
) -> dict[str, Any]:
    rate_limiter.check(x_api_key)
    project_id = db.scalar(select(Task.project_id).where(Task.id == task_id))
    if project_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    lock_project_for_write(
        db, project_id, current_user.id, ProjectRole.OWNER, ProjectRole.EDITOR,
        not_found_detail="Task not found",
    )
    task = db.scalar(
        select(Task).where(Task.id == task_id).execution_options(populate_existing=True)
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    db.delete(task)
    db.commit()

    return _success_response()


@router.get(
    "/projects",
    summary="List accessible projects",
    description=(
        "Return projects where the API-key user is a member."
    ),
    responses=AUTH_RESPONSES,
)
def list_public_projects(
    db: DatabaseSession,
    current_user: AuthenticatedApiUser,
    x_api_key: RawApiKey,
) -> dict[str, Any]:
    rate_limiter.check(x_api_key)
    projects = db.scalars(
        select(Project).where(_project_access_filter(current_user.id))
    ).all()

    return _success_response(
        projects=[_serialize_project(project) for project in projects]
    )


def _project_access_filter(user_id: UUID):
    member_project_ids = select(ProjectMember.project_id).where(
        ProjectMember.user_id == user_id
    )
    return Project.id.in_(member_project_ids)


def _serialize_task(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "project_id": task.project_id,
        "title": task.title,
        "description": task.description,
        "status": _enum_value(task.status),
        "assignee_id": task.assignee_id,
        "due_date": task.due_date,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def _serialize_project(project: Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "owner_id": project.owner_id,
        "created_at": project.created_at,
    }


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def _success_response(**data: Any) -> dict[str, Any]:
    return {"success": True, "data": data}
