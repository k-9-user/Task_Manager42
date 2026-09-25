from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task


def visible_project_ids(user_id: UUID):
    """Subquery of the projects the user is a member of."""

    return select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)


def get_membership_or_404(
    db: Session,
    project_id: UUID,
    user_id: UUID,
    not_found_detail: str = "Project not found",
) -> ProjectMember:
    membership = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    return membership


def lock_project_for_write(
    db: Session,
    project_id: UUID,
    user_id: UUID,
    *allowed_roles: ProjectRole,
    not_found_detail: str = "Project not found",
    forbidden_detail: str = "Project membership is read-only",
) -> Project:
    """Serialize project writes, then authorize against current membership."""

    project = db.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)

    membership = db.scalar(
        select(ProjectMember)
        .where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        .execution_options(populate_existing=True)
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    if membership.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=forbidden_detail)
    return project


def lock_task_for_write(
    db: Session,
    task_id: UUID,
    user_id: UUID,
    *allowed_roles: ProjectRole,
    not_found_detail: str = "Task not found",
    forbidden_detail: str = "Project membership is read-only",
) -> Task:
    """Lock the task's project for a write, then reload the task under that lock."""

    project_id = db.scalar(select(Task.project_id).where(Task.id == task_id))
    if project_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    lock_project_for_write(
        db, project_id, user_id, *allowed_roles,
        not_found_detail=not_found_detail, forbidden_detail=forbidden_detail,
    )
    task = db.scalar(
        select(Task).where(Task.id == task_id).execution_options(populate_existing=True)
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    return task
