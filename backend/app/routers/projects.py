"""
Router FastAPI pour les projets — cf 00-contrat-commun.md section 2
"Projects & Tasks — Owner : B".

⚠️ Ce fichier importe deux choses pas encore livrées par Personne A :
  - `app.database.get_db`            (session SQLAlchemy par requête)
  - `app.auth.dependencies.get_current_user` (user authentifié depuis le JWT)
Tant que A n'a pas livré ces fichiers, l'import de ce module échouera —
c'est attendu (cf SUIVI-PERSONNE-B.md et 02-fiche-personne-B.md).
"""

import html
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.notification import Notification, NotificationType
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.user import User
from app.schemas.common import SimpleSuccessResponse, SuccessEnvelope
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectMemberCreate,
    ProjectMemberResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.schemas.task import ProjectDetailResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Helpers de permission — réutilisés par routers/tasks.py également.
# ---------------------------------------------------------------------------


def _get_membership_or_404(
    db: Session, project_id: uuid.UUID, user_id: uuid.UUID
) -> ProjectMember:
    """Renvoie l'appartenance (avec son rôle) de `user_id` au projet `project_id`.

    On lève un 404 (pas un 403) si l'utilisateur n'est pas membre : ça évite
    de confirmer à quelqu'un l'existence d'un projet auquel il n'a pas accès
    (un 403 révélerait "ce projet existe mais tu n'as pas le droit", un 404
    ne révèle rien).
    """

    membership = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        .first()
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable"
        )
    return membership


def _require_role(membership: ProjectMember, *allowed: ProjectRole) -> None:
    """Lève 403 si le rôle du membre n'est pas dans `allowed`.

    Convention adoptée (à valider en groupe, cf SUIVI-PERSONNE-B.md point 2) :
    owner = tout, editor = gère les tâches, viewer = lecture seule.
    """

    if membership.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission refusée"
        )


# Module bonus notifications : on n'en crée pas pour un compte inactif depuis
# trop longtemps (évite d'accumuler des notifs qui ne seront jamais lues).
NOTIFICATION_INACTIVITY_THRESHOLD = timedelta(days=182)  # ~6 mois


def _user_is_notifiable(db: Session, user_id: uuid.UUID) -> bool:
    """Faux si le compte est inactif depuis plus de 6 mois.

    ⚠️ Approximation : le contrat commun n'a pas de champ `last_active_at` /
    `last_login_at` sur `users`, donc on utilise `User.updated_at` comme
    proxy — imprécis (ne bouge que si le profil est modifié, pas à chaque
    connexion/action), mais c'est la seule donnée dispo sans changer le
    schéma DB. À valider en équipe si un vrai champ de dernière activité
    serait préférable (impliquerait de le rajouter au contrat, côté A).

    `User.updated_at` est *timezone-aware* (`DateTime(timezone=True)` chez
    A) — on compare donc avec un "now" timezone-aware aussi, sinon
    `TypeError: can't subtract offset-naive and offset-aware datetimes`."""

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return False
    return datetime.now(timezone.utc) - user.updated_at <= NOTIFICATION_INACTIVITY_THRESHOLD


# ---------------------------------------------------------------------------
# GET /api/projects
# ---------------------------------------------------------------------------


@router.get("", response_model=SuccessEnvelope[ProjectListResponse])
def list_projects(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Liste les projets dont l'utilisateur connecté est membre (peu importe
    son rôle owner/editor/viewer) — pas tous les projets de la base.

    Hypothèse à confirmer avec l'équipe (le contrat ne le précise pas
    explicitement) : cf SUIVI-PERSONNE-B.md point 3.
    """

    projects = (
        db.query(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .filter(ProjectMember.user_id == current_user.id)
        .all()
    )
    return SuccessEnvelope(data=ProjectListResponse(projects=projects))


# ---------------------------------------------------------------------------
# POST /api/projects
# ---------------------------------------------------------------------------


@router.post(
    "", response_model=SuccessEnvelope[ProjectResponse], status_code=status.HTTP_201_CREATED
)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Crée un projet et ajoute automatiquement son créateur comme membre
    avec le rôle `owner`.

    Ce membership automatique n'est pas une route à part : c'est un détail
    d'implémentation nécessaire, sinon le créateur d'un projet ne pourrait
    jamais repasser la vérification `_get_membership_or_404` sur son propre
    projet.
    """

    project = Project(name=payload.name, description=payload.description, owner_id=current_user.id)
    db.add(project)
    db.flush()  # attribue project.id sans encore commit, pour créer le membership

    owner_membership = ProjectMember(
        project_id=project.id, user_id=current_user.id, role=ProjectRole.OWNER
    )
    db.add(owner_membership)
    db.commit()
    db.refresh(project)

    return SuccessEnvelope(data=ProjectResponse.model_validate(project))


# ---------------------------------------------------------------------------
# GET /api/projects/{id}
# ---------------------------------------------------------------------------


@router.get("/{project_id}", response_model=SuccessEnvelope[ProjectDetailResponse])
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _get_membership_or_404(db, project_id, current_user.id)

    project = (
        db.query(Project)
        .options(joinedload(Project.members), joinedload(Project.tasks))
        .filter(Project.id == project_id)
        .first()
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable")

    return SuccessEnvelope(
        data=ProjectDetailResponse(
            project=ProjectResponse.model_validate(project),
            members=[ProjectMemberResponse.model_validate(m) for m in project.members],
            tasks=[t for t in project.tasks],  # validé par le response_model
        )
    )


# ---------------------------------------------------------------------------
# PUT /api/projects/{id}
# ---------------------------------------------------------------------------


@router.put("/{project_id}", response_model=SuccessEnvelope[ProjectResponse])
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    membership = _get_membership_or_404(db, project_id, current_user.id)
    _require_role(membership, ProjectRole.OWNER)

    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable")

    # `exclude_unset=True` : on ne touche qu'aux champs réellement envoyés
    # par le client, pas ceux laissés à leur valeur par défaut (None).
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)

    return SuccessEnvelope(data=ProjectResponse.model_validate(project))


# ---------------------------------------------------------------------------
# DELETE /api/projects/{id}
# ---------------------------------------------------------------------------


@router.delete("/{project_id}", response_model=SimpleSuccessResponse)
def delete_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    membership = _get_membership_or_404(db, project_id, current_user.id)
    _require_role(membership, ProjectRole.OWNER)

    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable")

    # cascade="all, delete-orphan" sur Project.members et Project.tasks
    # (cf models/project.py) : SQLAlchemy supprime aussi les membres et
    # tâches associés.
    db.delete(project)
    db.commit()

    return SimpleSuccessResponse()


# ---------------------------------------------------------------------------
# POST /api/projects/{id}/members
# ---------------------------------------------------------------------------


@router.post(
    "/{project_id}/members",
    response_model=SuccessEnvelope[ProjectMemberResponse],
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    project_id: uuid.UUID,
    payload: ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    membership = _get_membership_or_404(db, project_id, current_user.id)
    _require_role(membership, ProjectRole.OWNER)

    new_member = ProjectMember(
        project_id=project_id, user_id=payload.user_id, role=payload.role
    )
    db.add(new_member)
    try:
        db.flush()
    except IntegrityError:
        # soit `user_id` n'existe pas (FK), soit il est déjà membre
        # (contrainte unique project_id+user_id) — cf models/project_member.py
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utilisateur introuvable ou déjà membre de ce projet",
        )

    # Module bonus notifications (cf 02-fiche-personne-B.md) : juste un
    # insert en DB, pas de nouvelle logique complexe. Sauf si le destinataire
    # est inactif depuis 6 mois (cf _user_is_notifiable).
    project = db.query(Project).filter(Project.id == project_id).first()
    if _user_is_notifiable(db, payload.user_id):
        db.add(
            Notification(
                user_id=payload.user_id,
                type=NotificationType.PROJECT_INVITE,
                content=f"Tu as été ajouté au projet « {html.escape(project.name)} »",
                related_task_id=None,
                related_project_id=project_id,
            )
        )
    db.commit()
    db.refresh(new_member)

    return SuccessEnvelope(data=ProjectMemberResponse.model_validate(new_member))


# ---------------------------------------------------------------------------
# DELETE /api/projects/{id}/members/{user_id}
# ---------------------------------------------------------------------------


@router.delete("/{project_id}/members/{user_id}", response_model=SimpleSuccessResponse)
def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    membership = _get_membership_or_404(db, project_id, current_user.id)
    _require_role(membership, ProjectRole.OWNER)

    target = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membre introuvable")

    if target.role == ProjectRole.OWNER:
        remaining_owners = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project_id,
                ProjectMember.role == ProjectRole.OWNER,
                ProjectMember.user_id != user_id,
            )
            .count()
        )
        if remaining_owners == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de retirer le dernier owner du projet",
            )

    db.delete(target)
    db.commit()

    return SimpleSuccessResponse()
