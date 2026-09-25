import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import Settings, get_settings
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
from app.models.user import UserStatus
from app.models.user_activity import UserActivity
from app.schemas.common import SimpleSuccessResponse, StrictRequest
from app.services.accounts import (
    ensure_another_active_admin,
    ensure_not_bootstrap_admin,
    hand_off_projects,
    lock_and_reload,
)
from app.services.gamification import build_summary
from app.services.uploads import remove_files
from app.utils.mailer import send_mail

router = APIRouter(prefix="/api/gdpr", tags=["gdpr"])


def _fmt_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return f"{value:%Y-%m-%d %H:%M} UTC"


def _fmt_date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _compact(row: dict) -> dict:
    """Retire les champs vides pour garder un export lisible."""

    return {key: value for key, value in row.items() if value not in (None, "", [])}


def _gamification_export(summary: dict, history: list[UserActivity]) -> dict | None:
    activity = {track["key"]: track["count"] for track in summary["tracks"] if track["count"]}
    if not activity and not history:
        return None
    return _compact({
        "xp": summary["progress"]["xp"],
        "level": summary["progress"]["level"],
        "title": summary["progress"]["badge"],
        "activity": activity or None,
        "activity_history": [
            {
                "type": item.track,
                "recorded_at": _fmt_dt(item.created_at),
            }
            for item in history
        ],
        "badges": [
            {"badge": badge["key"], "earned_at": _fmt_dt(badge["awarded_at"])}
            for badge in summary["badges"]
            if badge["awarded_at"] is not None
        ],
        "achievements": [
            {
                "achievement": achievement["key"],
                "xp": achievement["xp"],
                "unlocked_at": _fmt_dt(achievement["unlocked_at"]),
            }
            for track in summary["tracks"]
            for achievement in track["achievements"]
            if achievement["unlocked_at"] is not None
        ],
    })


@router.get("/export")
def export_my_data(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Exporte toutes les données personnelles de l'utilisateur connecté en
    un fichier JSON téléchargeable (droit à la portabilité RGPD).
    """

    user_id = current_user.id
    exported_at = datetime.now(timezone.utc)

    memberships = (
        db.query(ProjectMember)
        .options(joinedload(ProjectMember.project))
        .filter(ProjectMember.user_id == user_id)
        .order_by(ProjectMember.joined_at)
        .all()
    )
    member_project_ids = {m.project_id for m in memberships}
    owned_without_membership = [
        project
        for project in db.query(Project)
        .filter(Project.owner_id == user_id)
        .order_by(Project.created_at)
        .all()
        if project.id not in member_project_ids
    ]
    assigned_tasks = (
        db.query(Task)
        .options(joinedload(Task.project))
        .filter(Task.assignee_id == user_id, Task.project_id.in_(member_project_ids))
        .order_by(Task.created_at)
        .all()
    )
    comments = (
        db.query(Comment)
        .options(joinedload(Comment.task).joinedload(Task.project))
        .filter(Comment.author_id == user_id)
        .order_by(Comment.created_at)
        .all()
    )
    messages = (
        db.query(ProjectMessage)
        .options(joinedload(ProjectMessage.project))
        .filter(ProjectMessage.author_id == user_id)
        .order_by(ProjectMessage.created_at)
        .all()
    )
    uploads = (
        db.query(Attachment, Task.title, Project.name)
        .join(Task, Attachment.task_id == Task.id)
        .join(Project, Task.project_id == Project.id)
        .filter(Attachment.uploaded_by == user_id)
        .order_by(Attachment.created_at)
        .all()
    )
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at)
        .all()
    )
    api_keys = (
        db.query(ApiKey).filter(ApiKey.user_id == user_id).order_by(ApiKey.created_at).all()
    )
    gamification_history = list(
        db.scalars(
            select(UserActivity)
            .where(UserActivity.user_id == user_id)
            .order_by(UserActivity.created_at, UserActivity.id)
        )
    )

    export_data = {
        "about": {
            "service": "Task Manager 42",
            "exported_at": _fmt_dt(exported_at),
            "note": (
                "All personal data linked to your account. Passwords, API key "
                "values and file contents are never exported."
            ),
        },
        "profile": _compact({
            "email": current_user.email,
            "username": current_user.username,
            "display_name": current_user.display_name,
            "role": current_user.role.value,
            "sign_in": current_user.oauth_provider or "password",
            "avatar_url": current_user.avatar_url,
            "member_since": _fmt_dt(current_user.created_at),
            "last_updated": _fmt_dt(current_user.updated_at),
        }),
        "projects": [
            _compact({
                "name": m.project.name,
                "description": m.project.description,
                "your_role": m.role.value,
                "owner": m.project.owner_id == user_id,
                "joined_at": _fmt_dt(m.joined_at),
            })
            for m in memberships
        ] + [
            _compact({
                "name": p.name,
                "description": p.description,
                "your_role": ProjectRole.OWNER.value,
                "owner": True,
            })
            for p in owned_without_membership
        ],
        "assigned_tasks": [
            _compact({
                "title": t.title,
                "description": t.description,
                "project": t.project.name,
                "status": t.status.value,
                "due_date": _fmt_date(t.due_date),
            })
            for t in assigned_tasks
        ],
        "comments": [
            _compact({
                "task": c.task.title,
                "project": c.task.project.name,
                "text": c.content,
                "written_at": _fmt_dt(c.created_at),
                "edited_at": (
                    _fmt_dt(c.updated_at)
                    if c.updated_at and c.updated_at != c.created_at
                    else None
                ),
            })
            for c in comments
        ],
        "project_messages": [
            {
                "project": m.project.name,
                "text": m.content,
                "written_at": _fmt_dt(m.created_at),
            }
            for m in messages
        ],
        "uploaded_files": [
            {
                "file_name": attachment.file_name,
                "task": task_title,
                "project": project_name,
                "uploaded_at": _fmt_dt(attachment.created_at),
            }
            for attachment, task_title, project_name in uploads
        ],
        "notifications": [
            {
                "type": n.type.value,
                "text": n.content,
                "read": n.read,
                "received_at": _fmt_dt(n.created_at),
            }
            for n in notifications
        ],
        "api_keys": [{"created_at": _fmt_dt(k.created_at)} for k in api_keys],
        "gamification": _gamification_export(
            build_summary(db, user_id), gamification_history
        ),
    }
    export_data = {key: value for key, value in export_data.items() if value}

    body = json.dumps(export_data, indent=2, ensure_ascii=False)
    background_tasks.add_task(
        send_mail,
        current_user.email,
        "Your Task Manager data export",
        f"Hello {current_user.username},\n\n"
        f"A copy of your personal data was exported from your account on {_fmt_dt(exported_at)}.\n\n"
        "If you did not request it, change your password and contact an administrator.\n",
    )
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=gdpr_export.json",
            "Cache-Control": "no-store",
        },
    )


class GDPRDeleteRequest(StrictRequest):
    confirm: bool
    confirm_username: str


@router.delete("/account", response_model=SimpleSuccessResponse)
def delete_my_account(
    payload: GDPRDeleteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    settings: Settings = Depends(get_settings),
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

    current_user = lock_and_reload(db, current_user)
    if current_user.status == UserStatus.BANNED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned")
    ensure_not_bootstrap_admin(current_user)
    if payload.confirm_username != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username confirmation does not match",
        )
    ensure_another_active_admin(db, current_user, "At least one active administrator is required")

    files = hand_off_projects(db, current_user.id, settings)

    email, username = current_user.email, current_user.username
    db.delete(current_user)
    db.commit()
    remove_files(files)

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
