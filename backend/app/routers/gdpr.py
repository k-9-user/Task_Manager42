"""
Router FastAPI pour le module GDPR — cf 00-contrat-commun.md section 2
"Projects & Tasks — Owner : B".

Mêmes dépendances non livrées que routers/projects.py : `app.database.get_db`,
`app.auth.dependencies.get_current_user`.
"""

import json
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task
from app.schemas.common import SimpleSuccessResponse

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

    Décision prise pour combler un point non précisé par le contrat (cf
    SUIVI-PERSONNE-B.md) : le contenu de l'export couvre le profil (sans
    `password_hash`, jamais exporté), les projets possédés, les projets où
    l'utilisateur est simple membre, et les tâches qui lui sont assignées.
    À valider en équipe.
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


class GDPRDeleteRequest(BaseModel):
    confirm: bool


@router.delete("/account", response_model=SimpleSuccessResponse)
def delete_my_account(
    payload: GDPRDeleteRequest,
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
      lui-même). Ce membre est promu `owner` si besoin. **Convention
      "le plus ancien" par défaut à valider si l'équipe préfère un autre
      critère (le plus récent, un vote, etc.).**
    - si le projet n'a plus aucun autre membre, il est supprimé en cascade
      (members + tasks, cf `cascade="all, delete-orphan"` sur `Project`) ;
    - ses appartenances (`project_members`) dans des projets d'AUTRES owners
      sont simplement retirées, ces projets restent intacts ;
    - les tâches qui lui étaient assignées ailleurs gardent leur `assignee_id`
      remis à `NULL` (pas supprimées : ce ne sont pas SES données).
    """

    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation requise (confirm: true) pour supprimer le compte",
        )

    db.query(Task).filter(Task.assignee_id == current_user.id).update(
        {"assignee_id": None}
    )

    owned_projects = db.query(Project).filter(Project.owner_id == current_user.id).all()
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

    db.query(ProjectMember).filter(ProjectMember.user_id == current_user.id).delete()

    db.delete(current_user)
    db.commit()

    return SimpleSuccessResponse()
