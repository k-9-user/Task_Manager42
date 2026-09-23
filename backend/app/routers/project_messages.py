import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.project_member import ProjectRole
from app.models.project_message import ProjectMessage
from app.models.user import User
from app.routers.projects import _get_membership_or_404
from app.schemas.common import SimpleSuccessResponse, SuccessEnvelope
from app.schemas.project_message import (
    ProjectMessageCreate,
    ProjectMessageData,
    ProjectMessageListResponse,
    ProjectMessageResponse,
)

router = APIRouter(tags=["project-messages"])

DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]


def _serialize_message(message: ProjectMessage) -> ProjectMessageResponse:
    return ProjectMessageResponse(
        id=message.id,
        project_id=message.project_id,
        author_id=message.author_id,
        author_username=message.author.username,
        content=message.content,
        created_at=message.created_at,
    )


@router.get(
    "/api/projects/{project_id}/messages",
    response_model=SuccessEnvelope[ProjectMessageListResponse],
)
def list_project_messages(
    project_id: uuid.UUID,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
):
    _get_membership_or_404(db, project_id, current_user.id)

    messages = db.scalars(
        select(ProjectMessage)
        .where(ProjectMessage.project_id == project_id)
        .order_by(ProjectMessage.created_at.asc())
    ).all()

    return SuccessEnvelope(
        data=ProjectMessageListResponse(
            messages=[_serialize_message(m) for m in messages]
        )
    )


@router.post(
    "/api/projects/{project_id}/messages",
    response_model=SuccessEnvelope[ProjectMessageData],
    status_code=status.HTTP_201_CREATED,
)
def create_project_message(
    project_id: uuid.UUID,
    payload: ProjectMessageCreate,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
):
    _get_membership_or_404(db, project_id, current_user.id)

    message = ProjectMessage(
        project_id=project_id, author_id=current_user.id, content=payload.content
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    return SuccessEnvelope(
        data=ProjectMessageData(message=_serialize_message(message))
    )


@router.delete(
    "/api/project-messages/{message_id}",
    response_model=SimpleSuccessResponse,
)
def delete_project_message(
    message_id: uuid.UUID,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
):
    message = db.scalar(
        select(ProjectMessage).where(ProjectMessage.id == message_id)
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    membership = _get_membership_or_404(db, message.project_id, current_user.id)

    if message.author_id != current_user.id and membership.role != ProjectRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the message author or the project owner may delete this message",
        )

    db.delete(message)
    db.commit()

    return SimpleSuccessResponse()
