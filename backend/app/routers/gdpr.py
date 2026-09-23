"""
Router FastAPI pour le module GDPR (Owner : B).

- `GET /api/gdpr/export` : droit d'accès et portabilité (Art. 15 / 20).
- `DELETE /api/gdpr/account` : droit à l'effacement (Art. 17), body
  `{"confirm": true, "confirm_username": "<username exact>"}`.

Chaque opération envoie un email de confirmation (Mailpit en local), après
le commit, sans jamais faire échouer l'opération si l'envoi échoue.
"""

import json
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.project_permissions import lock_user_projects_for_write
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.api_key import ApiKey
from app.models.attachment import Attachment
from app.models.comment import Comment
from app.models.notification import Notification
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.project_message import ProjectMessage
from app.models.task import Task
from app.models.user import User, UserRole, UserStatus
from app.schemas.common import SimpleSuccessResponse, StrictRequest
from app.utils.locks import lock_admin_invariants
from app.utils.mailer import send_mail

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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Exporte toutes les données personnelles de l'utilisateur connecté en
    un fichier JSON téléchargeable (droit à la portabilité RGPD).

    L'export couvre toutes les lignes rattachées à l'utilisateur : profil,
    projets possédés, appartenances, tâches assignées, commentaires, messages
    de projet, métadonnées des pièces jointes envoyées, notifications et
    métadonnées des clés API. Jamais exportés : `password_hash`, `key_hash`,
    `oauth_id`, contenu binaire des fichiers.
    """

    owned_projects = db.query(Project).filter(Project.owner_id == current_user.id).all()

    memberships = (
        db.query(ProjectMember).filter(ProjectMember.user_id == current_user.id).all()
    )

    assigned_tasks = db.query(Task).filter(Task.assignee_id == current_user.id).all()
    comments = db.query(Comment).filter(Comment.author_id == current_user.id).all()
    messages = db.query(ProjectMessage).filter(ProjectMessage.author_id == current_user.id).all()
    attachments = db.query(Attachment).filter(Attachment.uploaded_by == current_user.id).all()
    notifications = db.query(Notification).filter(Notification.user_id == current_user.id).all()
    api_keys = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).all()

    export_data = {
        "exported_at": datetime.now(timezone.utc),
        "profile": {
            "id": current_user.id,
            "email": current_user.email,
            "username": current_user.username,
            "display_name": current_user.display_name,
            "role": current_user.role,
            "status": current_user.status,
            "oauth_provider": current_user.oauth_provider,
            "avatar_url": current_user.avatar_url,
            "created_at": current_user.created_at,
            "updated_at": current_user.updated_at,
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
            {"project_id": m.project_id, "role": m.role, "joined_at": m.joined_at}
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
        "comments": [
            {
                "id": c.id,
                "task_id": c.task_id,
                "content": c.content,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            }
            for c in comments
        ],
        "project_messages": [
            {
                "id": m.id,
                "project_id": m.project_id,
                "content": m.content,
                "created_at": m.created_at,
            }
            for m in messages
        ],
        "attachments_uploaded": [
            {
                "id": a.id,
                "task_id": a.task_id,
                "file_name": a.file_name,
                "created_at": a.created_at,
            }
            for a in attachments
        ],
        "notifications": [
            {
                "id": n.id,
                "type": n.type,
                "content": n.content,
                "read": n.read,
                "created_at": n.created_at,
            }
            for n in notifications
        ],
        "api_keys": [{"id": k.id, "created_at": k.created_at} for k in api_keys],
    }

    body = json.dumps(export_data, default=_json_default, indent=2, ensure_ascii=False)
    background_tasks.add_task(
        send_mail,
        current_user.email,
        "Your Task Manager data export",
        f"Hello {current_user.username},\n\n"
        "A copy of your personal data was exported from your account "
        f"on {export_data['exported_at']:%Y-%m-%d %H:%M} UTC.\n\n"
        "If you did not request it, change your password and contact an administrator.\n",
    )
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
    confirm_username: str


@router.delete("/account", response_model=SimpleSuccessResponse)
def delete_my_account(
    payload: GDPRDeleteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Supprime le compte de l'utilisateur connecté (droit à l'effacement RGPD).

    Décision prise pour combler un point non précisé par le contrat (cf
    SUIVI-PERSONNE-B.md), validée en équipe le 2026-08-18 :
    - pour un projet qu'il possède (`Project.owner_id`), s'il reste d'autres
      membres : la propriété est TRANSFÉRÉE (pas de suppression) — priorité à
      un autre membre ayant déjà le rôle `owner` s'il y en a un, sinon le
      membre restant le plus ancien (`ProjectMember.id` le plus petit, hors
      lui-même, `ProjectMember.joined_at` puis `id`). Ce membre est promu
      `owner` si besoin.
    - si le projet n'a plus aucun autre membre, il est supprimé en cascade
      (members + tasks, cf `cascade="all, delete-orphan"` sur `Project`) ;
    - ses appartenances (`project_members`) dans des projets d'AUTRES owners
      sont simplement retirées, ces projets restent intacts ;
    - les tâches qui lui étaient assignées ailleurs gardent leur `assignee_id`
      remis à `NULL` (pas supprimées : ce ne sont pas SES données) ;
    - les pièces jointes qu'il a envoyées restent dans leur projet avec
      `uploaded_by` remis à `NULL` (FK `ON DELETE SET NULL`) ;
    - commentaires, messages, notifications et clés API sont supprimés en
      cascade par la base.
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
    if payload.confirm_username != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username confirmation does not match",
        )
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
            .order_by(ProjectMember.joined_at, ProjectMember.id)
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

    # Flush transfers/deleted projects before bulk membership removal (autoflush
    # is disabled), so the ORM cannot later delete already-removed memberships.
    db.flush()
    db.query(ProjectMember).filter(ProjectMember.user_id == current_user.id).delete()

    email, username = current_user.email, current_user.username
    db.delete(current_user)
    db.commit()

    background_tasks.add_task(
        send_mail,
        email,
        "Your Task Manager account was deleted",
        f"Hello {username},\n\n"
        "Your account and the personal data attached to it were permanently deleted.\n"
        "Projects you shared were handed to another member; files you uploaded stay "
        "in their project without your name.\n\n"
        "If you did not request this, contact an administrator.\n",
    )
    return SimpleSuccessResponse()
