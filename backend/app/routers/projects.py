import html
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user
from app.auth.project_permissions import get_membership_or_404, lock_project_for_write
from app.config import Settings, get_settings
from app.database import get_db
from app.models.notification import Notification, NotificationType
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task
from app.schemas.common import SimpleSuccessResponse, SuccessEnvelope
from app.schemas.project import (
    ProjectCreate,
    ProjectData,
    ProjectListResponse,
    ProjectMemberCreate,
    ProjectMemberData,
    ProjectMemberResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.schemas.task import ProjectDetailResponse
from app.services.gamification import Rank, Track, ranks_for, record_activity
from app.services.uploads import remove_files, task_files

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _serialize_member(member: ProjectMember, rank: Rank) -> ProjectMemberResponse:
    """`ProjectMemberResponse` inclut username/email (pas juste user_id) pour que
    le frontend puisse afficher qui participe au projet sans appel supplémentaire
    — `member.user` est chargé via la relation SQLAlchemy."""

    return ProjectMemberResponse(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role,
        username=member.user.username,
        email=member.user.email,
        level=rank.level,
        badge=rank.badge,
    )


@router.get("", response_model=SuccessEnvelope[ProjectListResponse])
def list_projects(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Liste les projets dont l'utilisateur connecté est membre (peu importe
    son rôle owner/editor/viewer) — pas tous les projets de la base.
    """

    projects = (
        db.query(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .filter(ProjectMember.user_id == current_user.id)
        .all()
    )
    return SuccessEnvelope(data=ProjectListResponse(projects=projects))


@router.post(
    "", response_model=SuccessEnvelope[ProjectData], status_code=status.HTTP_201_CREATED
)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Crée un projet et ajoute automatiquement son créateur comme membre
    avec le rôle `owner`.
    """

    project = Project(name=payload.name, description=payload.description, owner_id=current_user.id)
    db.add(project)
    db.flush()

    owner_membership = ProjectMember(
        project_id=project.id, user_id=current_user.id, role=ProjectRole.OWNER
    )
    db.add(owner_membership)
    record_activity(db, current_user.id, Track.PROJECTS, project.id)
    db.commit()
    db.refresh(project)

    return SuccessEnvelope(data=ProjectData(project=ProjectResponse.model_validate(project)))


@router.get("/{project_id}", response_model=SuccessEnvelope[ProjectDetailResponse])
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    get_membership_or_404(db, project_id, current_user.id)

    project = (
        db.query(Project)
        .options(
            joinedload(Project.members).joinedload(ProjectMember.user),
            joinedload(Project.tasks),
        )
        .filter(Project.id == project_id)
        .first()
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable")

    ranks = ranks_for(db, [m.user_id for m in project.members])
    return SuccessEnvelope(
        data=ProjectDetailResponse(
            project=ProjectResponse.model_validate(project),
            members=[_serialize_member(m, ranks[m.user_id]) for m in project.members],
            tasks=project.tasks,
        )
    )


@router.put("/{project_id}", response_model=SuccessEnvelope[ProjectData])
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project = lock_project_for_write(
        db, project_id, current_user.id, ProjectRole.OWNER,
        not_found_detail="Projet introuvable", forbidden_detail="Permission refusée",
    )

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)

    return SuccessEnvelope(data=ProjectData(project=ProjectResponse.model_validate(project)))


@router.delete("/{project_id}", response_model=SimpleSuccessResponse)
def delete_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    project = lock_project_for_write(
        db, project_id, current_user.id, ProjectRole.OWNER,
        not_found_detail="Projet introuvable", forbidden_detail="Permission refusée",
    )

    files = task_files(db, settings, Task.project_id == project.id)
    db.delete(project)
    db.commit()
    remove_files(files)

    return SimpleSuccessResponse()


@router.post(
    "/{project_id}/members",
    response_model=SuccessEnvelope[ProjectMemberData],
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    project_id: uuid.UUID,
    payload: ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project = lock_project_for_write(
        db, project_id, current_user.id, ProjectRole.OWNER,
        not_found_detail="Projet introuvable", forbidden_detail="Permission refusée",
    )

    new_member = ProjectMember(
        project_id=project_id, user_id=payload.user_id, role=payload.role
    )
    db.add(new_member)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utilisateur introuvable ou déjà membre de ce projet",
        )

    db.add(
        Notification(
            user_id=payload.user_id,
            type=NotificationType.PROJECT_INVITE,
            content=f"Tu as été ajouté au projet « {html.escape(project.name)} »",
            related_task_id=None,
            related_project_id=project_id,
        )
    )
    record_activity(db, current_user.id, Track.COLLABORATORS, payload.user_id)
    db.commit()
    db.refresh(new_member)

    rank = ranks_for(db, [new_member.user_id])[new_member.user_id]
    return SuccessEnvelope(data=ProjectMemberData(member=_serialize_member(new_member, rank)))


@router.delete("/{project_id}/members/{user_id}", response_model=SimpleSuccessResponse)
def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project = lock_project_for_write(
        db, project_id, current_user.id, ProjectRole.OWNER,
        not_found_detail="Projet introuvable", forbidden_detail="Permission refusée",
    )

    target = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membre introuvable")

    if target.role == ProjectRole.OWNER:
        successor = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project_id,
                ProjectMember.role == ProjectRole.OWNER,
                ProjectMember.user_id != user_id,
            )
            .order_by(ProjectMember.id)
            .first()
        )
        if successor is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de retirer le dernier owner du projet",
            )
        if project.owner_id == user_id:
            project.owner_id = successor.user_id

    db.query(Task).filter(Task.project_id == project_id, Task.assignee_id == user_id).update(
        {"assignee_id": None}
    )
    db.delete(target)
    db.commit()

    return SimpleSuccessResponse()
