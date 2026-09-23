import json
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.project_permissions import lock_user_projects_for_write
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task
from app.models.user import User, UserRole, UserStatus
from app.schemas.common import SimpleSuccessResponse, StrictRequest
from app.utils.locks import lock_admin_invariants

router = APIRouter(prefix="/api/gdpr", tags=["gdpr"])


def _json_default(value):
    """Convertit UUID/date/datetime en str pour `json.dumps` — ces types ne
    sont pas sérialisables nativement en JSON."""

    if isinstance(value, (uuid.UUID, date, datetime)):
        return str(value)
    raise TypeError(f"Type non sérialisable : {type(value)}")


# ---------------------------------------------------------------------------
# GET /api/gdpr/export
# ---------------------------------------------------------------------------


@router.get("/export")
def export_my_data(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Exporte toutes les données personnelles de l'utilisateur connecté en
    un fichier JSON téléchargeable (droit à la portabilité RGPD).
    """

    owned_projects = db.query(Project).filter(Project.owner_id == current_user.id).all()

    memberships = (
        db.query(ProjectMember).filter(ProjectMember.user_id == current_user.id).all()
    )

    assigned_tasks = db.query(Task).filter(Task.assignee_id == current_user.id).all()

    export_data = {
        "profile": {
            "id": current_user.id,
            "email": current_user.email,
            "username": current_user.username,
            "role": current_user.role,
            "avatar_url": current_user.avatar_url,
            "created_at": current_user.created_at,
        },
        "owned_projects": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "created_at": p.created_at,
            }
            for p in owned_projects
        ],
        "project_memberships": [
            {"project_id": m.project_id, "role": m.role}
            for m in memberships
        ],
        "assigned_tasks": [
            {
                "id": t.id,
                "project_id": t.project_id,
                "title": t.title,
                "status": t.status,
                "due_date": t.due_date,
            }
            for t in assigned_tasks
        ],
    }

    body = json.dumps(export_data, default=_json_default, indent=2, ensure_ascii=False)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=gdpr_export.json"},
    )


# ---------------------------------------------------------------------------
# DELETE /api/gdpr/account
# ---------------------------------------------------------------------------


class GDPRDeleteRequest(StrictRequest):
    confirm: bool


@router.delete("/account", response_model=SimpleSuccessResponse)
def delete_my_account(
    payload: GDPRDeleteRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Supprime le compte de l'utilisateur connecté (droit à l'effacement RGPD).

    Les projets sans autre membre sont supprimés; sinon leur propriété est
    transférée. Les appartenances sont retirées et les tâches assignées sont
    conservées avec ``assignee_id`` remis à ``NULL``.
    """

    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation requise (confirm: true) pour supprimer le compte",
        )

    lock_admin_invariants(db)
    current_user = db.scalar(
        select(User)
        .where(User.id == current_user.id)
        .execution_options(populate_existing=True)
    )
    if current_user is None:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user.status == UserStatus.BANNED:
        raise HTTPException(status_code=403, detail="Account is banned")
    if current_user.role == UserRole.ADMIN:
        active_admins = db.scalar(
            select(func.count()).select_from(User).where(
                User.role == UserRole.ADMIN,
                User.status == UserStatus.ACTIVE,
            )
        ) or 0
        if active_admins <= 1:
            raise HTTPException(
                status_code=409,
                detail="At least one active administrator is required",
            )

    locked_projects = lock_user_projects_for_write(db, current_user.id)

    db.query(Task).filter(Task.assignee_id == current_user.id).update(
        {"assignee_id": None}
    )

    owned_projects = [
        project for project in locked_projects if project.owner_id == current_user.id
    ]
    for project in owned_projects:
        other_members = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id != current_user.id,
            )
            .order_by(ProjectMember.id)
            .all()
        )

        if not other_members:
            db.delete(project)
            continue

        successor = next(
            (m for m in other_members if m.role == ProjectRole.OWNER), other_members[0]
        )
        successor.role = ProjectRole.OWNER
        project.owner_id = successor.user_id

    db.flush()
    db.query(ProjectMember).filter(ProjectMember.user_id == current_user.id).delete()

    db.delete(current_user)
    db.commit()

    return SimpleSuccessResponse()
