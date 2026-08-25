import enum
import uuid

from sqlalchemy import Column, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ProjectRole(str, enum.Enum):
    """Rôle d'un membre au sein d'un projet précis (pas le rôle global user/admin)."""

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class ProjectMember(Base):
    """
    Table `project_members` — cf 00-contrat-commun.md section 1.
    Table de liaison project <-> user avec un rôle par membre.
    Utilisée pour vérifier les permissions (ex: un viewer ne peut pas
    modifier une tâche, cf semaine 3).
    """

    __tablename__ = "project_members"
    __table_args__ = (
        # Un même utilisateur ne peut apparaître qu'une fois par projet.
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(Enum(ProjectRole), nullable=False, default=ProjectRole.VIEWER)

    # Relations
    project = relationship("Project", back_populates="members")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<ProjectMember project_id={self.project_id} user_id={self.user_id} role={self.role}>"
