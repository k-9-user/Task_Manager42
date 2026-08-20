from enum import Enum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task, TaskStatus
from app.models.user import User


router = APIRouter(
    prefix="/api/search",
    tags=["Search"],
)


def get_search_current_user() -> User:
    """Fail closed until the shared JWT current-user dependency is available."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Shared current-user authentication is not available",
    )


DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_search_current_user)]


@router.get(
    "/tasks",
    summary="Search accessible tasks",
    description=(
        "Search tasks in projects owned by or shared with the authenticated user. "
        "Visibility is enforced before filtering and pagination."
    ),
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Shared current-user authentication is not integrated."
        }
    },
)
def search_tasks(
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    q: Annotated[
        str | None,
        Query(description="Case-insensitive text searched in task title and description."),
    ] = None,
    task_status: Annotated[
        TaskStatus | None,
        Query(alias="status", description="Filter by task status."),
    ] = None,
    project_id: Annotated[
        UUID | None,
        Query(description="Filter by a specific visible project UUID."),
    ] = None,
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
        search_pattern = f"%{normalized_query}%"
        filters.append(
            or_(
                Task.title.ilike(search_pattern),
                Task.description.ilike(search_pattern),
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
    tasks = db.scalars(
        filtered_tasks
        .order_by(Task.created_at.desc(), Task.id.desc())
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


def _project_access_filter(user_id: UUID):
    member_project_ids = select(ProjectMember.project_id).where(
        ProjectMember.user_id == user_id
    )
    return or_(
        Project.owner_id == user_id,
        Project.id.in_(member_project_ids),
    )


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
