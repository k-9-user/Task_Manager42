"""
Router FastAPI pour les notifications — module bonus, cf 00-contrat-commun.md
section 2 "Projects & Tasks — Owner : B".

Mêmes dépendances non livrées que routers/projects.py : `app.database.get_db`,
`app.auth.dependencies.get_current_user`.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.notification import Notification
from app.schemas.common import SimpleSuccessResponse, SuccessEnvelope
from app.schemas.notification import NotificationListResponse, NotificationResponse

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=SuccessEnvelope[NotificationListResponse])
def list_notifications(
    unread_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.read.is_(False))

    notifications = query.order_by(Notification.created_at.desc()).all()

    return SuccessEnvelope(
        data=NotificationListResponse(
            notifications=[NotificationResponse.model_validate(n) for n in notifications],
            total=len(notifications),
        )
    )


@router.put("/{notification_id}/read", response_model=SuccessEnvelope[NotificationResponse])
def mark_notification_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification introuvable"
        )

    notification.read = True
    db.commit()
    db.refresh(notification)

    return SuccessEnvelope(data=NotificationResponse.model_validate(notification))


@router.put("/read-all", response_model=SimpleSuccessResponse)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.read.is_(False)
    ).update({"read": True})
    db.commit()

    return SimpleSuccessResponse()
