import enum
import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


DEFAULT_AVATAR_URL = "/static/default-avatar.png"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "oauth_provider IS NULL OR oauth_provider IN ('google', 'github')",
            name="ck_users_oauth_provider",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=True)
    oauth_provider = Column(String, nullable=True)
    oauth_id = Column(String, nullable=True)
    username = Column(String, unique=True, nullable=False)
    role = Column(
        Enum(
            UserRole,
            name="user_role",
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
        default=UserRole.USER,
        server_default=UserRole.USER.value,
    )
    avatar_url = Column(
        String,
        nullable=False,
        default=DEFAULT_AVATAR_URL,
        server_default=DEFAULT_AVATAR_URL,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
