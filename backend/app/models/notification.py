import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base, utc_now


class NotificationType(str, enum.Enum):
    TASK_ASSIGNED = "task_assigned"
    TASK_STATUS_CHANGED = "task_status_changed"
    PROJECT_INVITE = "project_invite"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(
        Enum(NotificationType, name="notificationtype", values_callable=lambda cls: [kind.value for kind in cls]),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    related_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    related_project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    read = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )

    user = relationship("User", foreign_keys=[user_id])
    related_task = relationship("Task", foreign_keys=[related_task_id])
    related_project = relationship("Project", foreign_keys=[related_project_id])

    def __repr__(self) -> str:
        return f"<Notification id={self.id} user_id={self.user_id} type={self.type}>"
