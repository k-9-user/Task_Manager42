"""
Schémas Pydantic pour l'API Notifications — module bonus, cf
00-contrat-commun.md section 2.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationType


class NotificationResponse(BaseModel):
    """Représentation d'une notification renvoyée par l'API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    type: NotificationType
    content: str
    related_task_id: Optional[uuid.UUID] = None
    related_project_id: Optional[uuid.UUID] = None
    read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Réponse de GET /api/notifications → `{notifications: [...], total: N}`."""

    notifications: list[NotificationResponse]
    total: int
