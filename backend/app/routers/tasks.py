import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.project_permissions import lock_project_for_write, lock_task_for_write
from app.config import Settings, get_settings
from app.database import get_db
from app.models.notification import Notification, NotificationType
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.schemas.common import SimpleSuccessResponse, SuccessEnvelope
from app.schemas.task import TaskCreate, TaskData, TaskResponse, TaskUpdate
from app.services.gamification import Track, record_activity
from app.services.uploads import remove_files, task_files

router = APIRouter(tags=["tasks"])

DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
ApplicationSettings = Annotated[Settings, Depends(get_settings)]


def _assert_valid_assignee(db: Session, project_id: uuid.UUID, assignee_id: uuid.UUID) -> None:
    membership = db.scalar(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == assignee_id
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignee must be a project member",
        )


def _notify(db: Session, task: Task, user_id: uuid.UUID, type_: NotificationType, content: str) -> None:
    db.add(
        Notification(
            user_id=user_id,
            type=type_,
            content=content,
            related_task_id=task.id,
            related_project_id=task.project_id,
        )
    )


@router.post(
    "/api/projects/{project_id}/tasks",
    response_model=SuccessEnvelope[TaskData],
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    project_id: uuid.UUID,
    payload: TaskCreate,
    db: DatabaseSession,
    current_user: CurrentUser,
):
    lock_project_for_write(
        db, project_id, current_user.id, ProjectRole.OWNER, ProjectRole.EDITOR,
        forbidden_detail="Permission denied",
    )
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
    db.flush()
    if task.assignee_id is not None:
        _notify(
            db, task, task.assignee_id, NotificationType.TASK_ASSIGNED,
            f'You were assigned to the task "{task.title}"',
        )
    record_activity(db, current_user.id, Track.TASKS_CREATED, task.id)
    db.commit()
    db.refresh(task)
    return SuccessEnvelope(data=TaskData(task=TaskResponse.model_validate(task)))


@router.put("/api/tasks/{task_id}", response_model=SuccessEnvelope[TaskData])
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: DatabaseSession,
    current_user: CurrentUser,
):
    task = lock_task_for_write(
        db, task_id, current_user.id, ProjectRole.OWNER, ProjectRole.EDITOR,
        forbidden_detail="Permission denied",
    )
    updates = payload.model_dump(exclude_unset=True)
    new_assignee = updates.get("assignee_id")
    if new_assignee is not None:
        _assert_valid_assignee(db, task.project_id, new_assignee)

    reassigned_to = new_assignee if new_assignee not in (None, task.assignee_id) else None
    status_changed = "status" in updates and updates["status"] != task.status

    for field, value in updates.items():
        setattr(task, field, value)

    if reassigned_to is not None:
        _notify(
            db, task, reassigned_to, NotificationType.TASK_ASSIGNED,
            f'You were assigned to the task "{task.title}"',
        )
    elif status_changed and task.assignee_id is not None:
        _notify(
            db, task, task.assignee_id, NotificationType.TASK_STATUS_CHANGED,
            f'Task "{task.title}" moved to status "{task.status.value}"',
        )

    if status_changed and task.status == TaskStatus.DONE:
        record_activity(db, current_user.id, Track.TASKS_COMPLETED, task.id)

    db.commit()
    db.refresh(task)
    return SuccessEnvelope(data=TaskData(task=TaskResponse.model_validate(task)))


@router.delete("/api/tasks/{task_id}", response_model=SimpleSuccessResponse)
def delete_task(
    task_id: uuid.UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
    settings: ApplicationSettings,
):
    task = lock_task_for_write(
        db, task_id, current_user.id, ProjectRole.OWNER, forbidden_detail="Permission denied",
    )
    files = task_files(db, settings, Task.id == task.id)
    db.delete(task)
    db.commit()
    remove_files(files)
    return SimpleSuccessResponse()
