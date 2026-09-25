import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ProjectRole(str, enum.Enum):
    """A member's role inside one project, distinct from the global user/admin role."""

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class ProjectMember(Base):
    """Project/user link with a role: the source of every project permission check."""

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(
        Enum(ProjectRole, name="projectrole", values_callable=lambda cls: [role.value for role in cls]),
        nullable=False,
        default=ProjectRole.VIEWER,
    )
    joined_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    project = relationship("Project", back_populates="members")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<ProjectMember project_id={self.project_id} user_id={self.user_id} role={self.role}>"
