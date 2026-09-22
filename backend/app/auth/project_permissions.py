from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task


def lock_user_projects_for_write(db: Session, user_id: UUID) -> list[Project]:
    """Lock every project the user owns, belongs to, or has an assignment in."""

    member_project_ids = select(ProjectMember.project_id).where(
        ProjectMember.user_id == user_id
    )
    assigned_project_ids = select(Task.project_id).where(Task.assignee_id == user_id)
    return list(
        db.scalars(
            select(Project)
            .where(
                or_(
                    Project.owner_id == user_id,
                    Project.id.in_(member_project_ids),
                    Project.id.in_(assigned_project_ids),
                )
            )
            .order_by(Project.id)
            .with_for_update()
        ).all()
    )


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
