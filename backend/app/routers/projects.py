import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth.dependencies import get_current_user
from app.auth.project_permissions import get_membership_or_404, lock_project_for_write
from app.config import Settings, get_settings
from app.database import get_db
from app.models.notification import Notification, NotificationType
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task
from app.models.user import User
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

DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
ApplicationSettings = Annotated[Settings, Depends(get_settings)]


def _serialize_member(member: ProjectMember, rank: Rank) -> ProjectMemberResponse:
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


def _lock_as_owner(db: Session, project_id: uuid.UUID, user: User) -> Project:
    return lock_project_for_write(
        db, project_id, user.id, ProjectRole.OWNER, forbidden_detail="Permission denied",
    )


@router.get("", response_model=SuccessEnvelope[ProjectListResponse])
def list_projects(db: DatabaseSession, current_user: CurrentUser):
    projects = db.scalars(
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == current_user.id)
    ).all()
    return SuccessEnvelope(data=ProjectListResponse(projects=projects))


@router.post(
    "", response_model=SuccessEnvelope[ProjectData], status_code=status.HTTP_201_CREATED
)
def create_project(payload: ProjectCreate, db: DatabaseSession, current_user: CurrentUser):
    """Create a project; its creator becomes its first owner member."""

    project = Project(name=payload.name, description=payload.description, owner_id=current_user.id)
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=current_user.id, role=ProjectRole.OWNER))
    record_activity(db, current_user.id, Track.PROJECTS, project.id)
    db.commit()
    db.refresh(project)
    return SuccessEnvelope(data=ProjectData(project=ProjectResponse.model_validate(project)))


@router.get("/{project_id}", response_model=SuccessEnvelope[ProjectDetailResponse])
def get_project(project_id: uuid.UUID, db: DatabaseSession, current_user: CurrentUser):
    get_membership_or_404(db, project_id, current_user.id)
    project = db.get(
        Project,
        project_id,
        options=[
            selectinload(Project.members).joinedload(ProjectMember.user),
            selectinload(Project.tasks),
        ],
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

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
    db: DatabaseSession,
    current_user: CurrentUser,
):
    project = _lock_as_owner(db, project_id, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return SuccessEnvelope(data=ProjectData(project=ProjectResponse.model_validate(project)))


@router.delete("/{project_id}", response_model=SimpleSuccessResponse)
def delete_project(
    project_id: uuid.UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
    settings: ApplicationSettings,
):
    project = _lock_as_owner(db, project_id, current_user)
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
    db: DatabaseSession,
    current_user: CurrentUser,
):
    project = _lock_as_owner(db, project_id, current_user)
    new_member = ProjectMember(project_id=project_id, user_id=payload.user_id, role=payload.role)
    db.add(new_member)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found or already a project member",
        )

    db.add(
        Notification(
            user_id=payload.user_id,
            type=NotificationType.PROJECT_INVITE,
            content=f'You were added to the project "{project.name}"',
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
    db: DatabaseSession,
    current_user: CurrentUser,
):
    project = _lock_as_owner(db, project_id, current_user)
    target = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if target.role == ProjectRole.OWNER:
        successor = db.scalar(
            select(ProjectMember)
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.role == ProjectRole.OWNER,
                ProjectMember.user_id != user_id,
            )
            .order_by(ProjectMember.id)
        )
        if successor is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last project owner",
            )
        if project.owner_id == user_id:
            project.owner_id = successor.user_id

    db.execute(
        update(Task)
        .where(Task.project_id == project_id, Task.assignee_id == user_id)
        .values(assignee_id=None)
    )
    db.delete(target)
    db.commit()
    return SimpleSuccessResponse()
