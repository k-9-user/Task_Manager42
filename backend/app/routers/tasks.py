import html
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.project_permissions import lock_project_for_write, lock_task_for_write
from app.config import Settings, get_settings
from app.database import get_db
from app.models.notification import Notification, NotificationType
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task, TaskStatus
from app.schemas.common import SimpleSuccessResponse, SuccessEnvelope
from app.schemas.task import TaskCreate, TaskData, TaskResponse, TaskUpdate
from app.services.gamification import Track, record_activity
from app.services.uploads import remove_files, task_files

router = APIRouter(tags=["tasks"])


def _assert_valid_assignee(db: Session, project_id: uuid.UUID, assignee_id: uuid.UUID) -> None:
    """Refuse d'assigner une tâche à quelqu'un qui n'est pas membre du projet."""

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


def _notify(
    db: Session,
    *,
    user_id: uuid.UUID,
    type_: NotificationType,
    content: str,
    task_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    db.add(
        Notification(
            user_id=user_id,
            type=type_,
            content=content,
            related_task_id=task_id,
            related_project_id=project_id,
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
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Seuls owner et editor peuvent créer une tâche — un viewer est en lecture seule"""

    lock_project_for_write(
        db, project_id, current_user.id, ProjectRole.OWNER, ProjectRole.EDITOR,
        not_found_detail="Projet introuvable", forbidden_detail="Permission refusée",
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
            db,
            user_id=task.assignee_id,
            type_=NotificationType.TASK_ASSIGNED,
            content=f"Tu as été assigné à la tâche « {html.escape(task.title)} »",
            task_id=task.id,
            project_id=project_id,
        )

    record_activity(db, current_user.id, Track.TASKS_CREATED, task.id)
    db.commit()
    db.refresh(task)

    return SuccessEnvelope(data=TaskData(task=TaskResponse.model_validate(task)))


@router.put("/api/tasks/{task_id}", response_model=SuccessEnvelope[TaskData])
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    task = lock_task_for_write(
        db, task_id, current_user.id, ProjectRole.OWNER, ProjectRole.EDITOR,
        not_found_detail="Tâche introuvable", forbidden_detail="Permission refusée",
    )

    updates = payload.model_dump(exclude_unset=True)

    if updates.get("assignee_id") is not None:
        _assert_valid_assignee(db, task.project_id, updates["assignee_id"])

    reassigned_to = (
        updates["assignee_id"]
        if "assignee_id" in updates
        and updates["assignee_id"] is not None
        and updates["assignee_id"] != task.assignee_id
        else None
    )
    status_changed = "status" in updates and updates["status"] != task.status

    for field, value in updates.items():
        setattr(task, field, value)

    if reassigned_to is not None:
        _notify(
            db,
            user_id=reassigned_to,
            type_=NotificationType.TASK_ASSIGNED,
            content=f"Tu as été assigné à la tâche « {html.escape(task.title)} »",
            task_id=task.id,
            project_id=task.project_id,
        )
    elif status_changed and task.assignee_id is not None:
        _notify(
            db,
            user_id=task.assignee_id,
            type_=NotificationType.TASK_STATUS_CHANGED,
            content=f"La tâche « {task.title} » est passée au statut « {task.status.value} »",
            task_id=task.id,
            project_id=task.project_id,
        )

    if status_changed and task.status == TaskStatus.DONE:
        record_activity(db, current_user.id, Track.TASKS_COMPLETED, task.id)

    db.commit()
    db.refresh(task)

    return SuccessEnvelope(data=TaskData(task=TaskResponse.model_validate(task)))


@router.delete("/api/tasks/{task_id}", response_model=SimpleSuccessResponse)
def delete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    task = lock_task_for_write(
        db, task_id, current_user.id, ProjectRole.OWNER,
        not_found_detail="Tâche introuvable", forbidden_detail="Permission refusée",
    )

    files = task_files(db, settings, Task.id == task.id)
    db.delete(task)
    db.commit()
    remove_files(files)

    return SimpleSuccessResponse()
