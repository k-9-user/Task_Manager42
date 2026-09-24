from enum import Enum
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.utils.validators import escape_like_pattern


router = APIRouter(
    prefix="/api/search",
    tags=["Search"],
)


DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]

TaskSortField = Literal["created_at", "title", "due_date", "status"]
ProjectSortField = Literal["created_at", "name"]
SortDirection = Literal["asc", "desc"]

TASK_SORT_COLUMNS = {
    "created_at": Task.created_at,
    "title": Task.title,
    "due_date": Task.due_date,
    "status": Task.status,
}
PROJECT_SORT_COLUMNS = {
    "created_at": Project.created_at,
    "name": Project.name,
}


def _ordered(column, direction: SortDirection, tie_breaker):
    primary = column.asc() if direction == "asc" else column.desc()
    return primary, tie_breaker.desc()


@router.get(
    "/tasks",
    summary="Search accessible tasks",
    description=(
        "Search tasks in projects where the authenticated user is a member. "
        "Visibility is enforced before filtering and pagination."
    ),
)
def search_tasks(
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    q: Annotated[
        str | None,
        Query(
            max_length=255,
            description="Case-insensitive text searched in task title and description.",
        ),
    ] = None,
    task_status: Annotated[
        TaskStatus | None,
        Query(alias="status", description="Filter by task status."),
    ] = None,
    project_id: Annotated[
        UUID | None,
        Query(description="Filter by a specific visible project UUID."),
    ] = None,
    sort: Annotated[
        TaskSortField,
        Query(description="Field to sort by: created_at, title, due_date or status."),
    ] = "created_at",
    direction: Annotated[
        SortDirection,
        Query(description="Sort direction: asc or desc."),
    ] = "desc",
    page: Annotated[
        int,
        Query(ge=1, description="One-based result page."),
    ] = 1,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Tasks returned per page, up to 100."),
    ] = 20,
) -> dict[str, Any]:
    filters = [_project_access_filter(current_user.id)]

    normalized_query = q.strip() if q is not None else ""
    if normalized_query:
        search_pattern = f"%{escape_like_pattern(normalized_query)}%"
        filters.append(
            or_(
                Task.title.ilike(search_pattern, escape="\\"),
                Task.description.ilike(search_pattern, escape="\\"),
            )
        )

    if task_status is not None:
        filters.append(Task.status == task_status)

    if project_id is not None:
        filters.append(Task.project_id == project_id)

    filtered_tasks = (
        select(Task)
        .join(Project, Task.project_id == Project.id)
        .where(*filters)
    )
    total = db.scalar(
        select(func.count()).select_from(filtered_tasks.subquery())
    ) or 0
    order_by = _ordered(TASK_SORT_COLUMNS[sort], direction, Task.id)
    tasks = db.scalars(
        filtered_tasks
        .order_by(*order_by)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return {
        "success": True,
        "data": {
            "tasks": [_serialize_task(task) for task in tasks],
            "total": total,
        },
    }


@router.get(
    "/projects",
    summary="Search accessible projects by name",
    description=(
        "Search projects the authenticated user is a member of, by name. "
        "Visibility is enforced before filtering and pagination."
    ),
)
def search_projects(
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    q: Annotated[
        str | None,
        Query(
            max_length=255,
            description="Case-insensitive text searched in the project name.",
        ),
    ] = None,
    sort: Annotated[
        ProjectSortField,
        Query(description="Field to sort by: created_at or name."),
    ] = "created_at",
    direction: Annotated[
        SortDirection,
        Query(description="Sort direction: asc or desc."),
    ] = "desc",
    page: Annotated[
        int,
        Query(ge=1, description="One-based result page."),
    ] = 1,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Projects returned per page, up to 100."),
    ] = 20,
) -> dict[str, Any]:
    filters = [_project_access_filter(current_user.id)]

    normalized_query = q.strip() if q is not None else ""
    if normalized_query:
        search_pattern = f"%{escape_like_pattern(normalized_query)}%"
        filters.append(Project.name.ilike(search_pattern, escape="\\"))

    filtered_projects = select(Project).where(*filters)
    total = db.scalar(
        select(func.count()).select_from(filtered_projects.subquery())
    ) or 0
    order_by = _ordered(PROJECT_SORT_COLUMNS[sort], direction, Project.id)
    projects = db.scalars(
        filtered_projects
        .order_by(*order_by)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return {
        "success": True,
        "data": {
            "projects": [_serialize_project(project) for project in projects],
            "total": total,
        },
    }


def _project_access_filter(user_id: UUID):
    member_project_ids = select(ProjectMember.project_id).where(
        ProjectMember.user_id == user_id
    )
    return Project.id.in_(member_project_ids)


def _serialize_project(project: Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "owner_id": project.owner_id,
        "created_at": project.created_at,
    }


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


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value
