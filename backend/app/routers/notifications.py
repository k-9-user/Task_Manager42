import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.common import SimpleSuccessResponse, SuccessEnvelope
from app.schemas.notification import NotificationData, NotificationListResponse, NotificationResponse

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=SuccessEnvelope[NotificationListResponse])
def list_notifications(db: DatabaseSession, current_user: CurrentUser, unread_only: bool = False):
    query = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        query = query.where(Notification.read.is_(False))
    notifications = db.scalars(query.order_by(Notification.created_at.desc())).all()
    return SuccessEnvelope(
        data=NotificationListResponse(
            notifications=[NotificationResponse.model_validate(n) for n in notifications],
            total=len(notifications),
        )
    )


@router.put("/{notification_id}/read", response_model=SuccessEnvelope[NotificationData])
def mark_notification_read(
    notification_id: uuid.UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
):
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == current_user.id
        )
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification.read = True
    db.commit()
    db.refresh(notification)
    return SuccessEnvelope(
        data=NotificationData(notification=NotificationResponse.model_validate(notification))
    )


@router.put("/read-all", response_model=SimpleSuccessResponse)
def mark_all_notifications_read(db: DatabaseSession, current_user: CurrentUser):
    db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.read.is_(False))
        .values(read=True)
    )
    db.commit()
    return SimpleSuccessResponse()
