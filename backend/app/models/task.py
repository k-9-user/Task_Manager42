import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, Date, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class TaskStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class Task(Base):
    """
    Table `tasks` — cf 00-contrat-commun.md section 1.
    Une tâche appartient à un projet, peut être assignée à un user,
    et peut avoir des attachments (modèle géré par Personne C).
    """

    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.TODO)
    assignee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    due_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relations
    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", foreign_keys=[assignee_id])

    # `attachments` sera exposé par le back_populates côté modèle de C
    # (backend/app/models/attachment.py), pas défini ici pour éviter
    # un import circulaire tant que C n'a pas livré son modèle.

    def __repr__(self) -> str:
        return f"<Task id={self.id} title={self.title!r} status={self.status}>"
