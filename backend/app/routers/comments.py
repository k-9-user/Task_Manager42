"""Router FastAPI pour les commentaires de tâche.

Un commentaire est un fil de discussion texte attaché à une tâche, en plus
des attachments (fichiers). N'importe quel membre du projet (owner, editor ou
viewer) peut lire et écrire des commentaires : ce n'est pas une modification
de la tâche elle-même, donc pas soumis à la même restriction owner/editor que
`update_task`. Seul l'auteur du commentaire (ou le owner du projet, pour
modération) peut le supprimer.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.comment import Comment
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task
from app.models.user import User
from app.routers.projects import _get_membership_or_404
from app.schemas.comment import CommentCreate, CommentData, CommentListResponse, CommentResponse
from app.schemas.common import SimpleSuccessResponse, SuccessEnvelope

router = APIRouter(tags=["comments"])

DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]


def _task_project_id_or_404(db: Session, task_id: uuid.UUID) -> uuid.UUID:
    project_id = db.scalar(select(Task.project_id).where(Task.id == task_id))
    if project_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return project_id


@router.get(
    "/api/tasks/{task_id}/comments",
    response_model=SuccessEnvelope[CommentListResponse],
)
def list_comments(
    task_id: uuid.UUID,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
):
    project_id = _task_project_id_or_404(db, task_id)
    _get_membership_or_404(db, project_id, current_user.id)

    comments = db.scalars(
        select(Comment)
        .where(Comment.task_id == task_id)
        .order_by(Comment.created_at.asc())
    ).all()

    return SuccessEnvelope(
        data=CommentListResponse(
            comments=[CommentResponse.model_validate(c) for c in comments]
        )
    )


@router.post(
    "/api/tasks/{task_id}/comments",
    response_model=SuccessEnvelope[CommentData],
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    task_id: uuid.UUID,
    payload: CommentCreate,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
):
    project_id = _task_project_id_or_404(db, task_id)
    _get_membership_or_404(db, project_id, current_user.id)

    comment = Comment(task_id=task_id, author_id=current_user.id, content=payload.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return SuccessEnvelope(data=CommentData(comment=CommentResponse.model_validate(comment)))


@router.delete(
    "/api/comments/{comment_id}",
    response_model=SimpleSuccessResponse,
)
def delete_comment(
    comment_id: uuid.UUID,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
):
    comment = db.scalar(select(Comment).where(Comment.id == comment_id))
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    project_id = _task_project_id_or_404(db, comment.task_id)
    membership = _get_membership_or_404(db, project_id, current_user.id)

    if comment.author_id != current_user.id and membership.role != ProjectRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the comment author or the project owner may delete this comment",
        )

    db.delete(comment)
    db.commit()

    return SimpleSuccessResponse()
