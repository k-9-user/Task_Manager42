import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class NotificationType(str, enum.Enum):
    TASK_ASSIGNED = "task_assigned"
    TASK_STATUS_CHANGED = "task_status_changed"
    PROJECT_INVITE = "project_invite"


class Notification(Base):
    """
    Table `notifications` — cf 00-contrat-commun.md section 1 (module bonus).
    Une notification appartient à son destinataire (`user_id`) et référence
    optionnellement la tâche/le projet concerné.
    """

    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(Enum(NotificationType), nullable=False)
    content = Column(Text, nullable=False)
    related_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    related_project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relations
    user = relationship("User", foreign_keys=[user_id])
    related_task = relationship("Task", foreign_keys=[related_task_id])
    related_project = relationship("Project", foreign_keys=[related_project_id])

    def __repr__(self) -> str:
        return f"<Notification id={self.id} user_id={self.user_id} type={self.type}>"
