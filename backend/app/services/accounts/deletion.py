from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.project_permissions import lock_user_projects_for_write
from app.config import Settings
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task
from app.services.uploads import task_files


def hand_off_projects(db: Session, user_id: UUID, settings: Settings) -> list[Path]:
    """Detach a departing user from every project; return the files to remove after commit.

    Projects without another member are deleted; otherwise their ownership goes to an
    existing owner, else the oldest member. Assigned tasks are kept, unassigned.
    """

    locked_projects = lock_user_projects_for_write(db, user_id)

    db.query(Task).filter(Task.assignee_id == user_id).update(
        {"assignee_id": None}
    )

    owned_projects = [
        project for project in locked_projects if project.owner_id == user_id
    ]
    files = []
    for project in owned_projects:
        other_members = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id != user_id,
            )
            .order_by(ProjectMember.joined_at, ProjectMember.id)
            .all()
        )

        if not other_members:
            files += task_files(db, settings, Task.project_id == project.id)
            db.delete(project)
            continue

        successor = next(
            (m for m in other_members if m.role == ProjectRole.OWNER), other_members[0]
        )
        successor.role = ProjectRole.OWNER
        project.owner_id = successor.user_id

    db.flush()
    db.query(ProjectMember).filter(ProjectMember.user_id == user_id).delete()
    return files
