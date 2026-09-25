from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.project_permissions import visible_project_ids
from app.database import get_db
from app.models.project import Project
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.schemas.common import SuccessEnvelope
from app.schemas.project import ProjectResponse
from app.schemas.task import TaskSummary
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
) -> SuccessEnvelope:
    filters = [Task.project_id.in_(visible_project_ids(current_user.id))]

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

    filtered_tasks = select(Task).where(*filters)
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

    return SuccessEnvelope(
        data={"tasks": [TaskSummary.model_validate(task) for task in tasks], "total": total}
    )


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
) -> SuccessEnvelope:
    filters = [Project.id.in_(visible_project_ids(current_user.id))]

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

    return SuccessEnvelope(
        data={
            "projects": [ProjectResponse.model_validate(project) for project in projects],
            "total": total,
        }
    )
