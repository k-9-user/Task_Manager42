import enum
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


DEFAULT_AVATAR_URL = "/static/default-avatar.png"
ADMIN_INVARIANT_LOCK_KEY = 0x544D3432


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    BANNED = "banned"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "oauth_provider IS NULL OR oauth_provider IN ('google', 'github')",
            name="ck_users_oauth_provider",
        ),
        CheckConstraint(
            "(oauth_provider IS NULL AND oauth_id IS NULL) OR "
            "(oauth_provider IS NOT NULL AND oauth_id IS NOT NULL)",
            name="ck_users_oauth_pair",
        ),
        CheckConstraint(
            "password_hash IS NOT NULL OR "
            "(oauth_provider IS NOT NULL AND oauth_id IS NOT NULL)",
            name="ck_users_auth_method",
        ),
        UniqueConstraint(
            "oauth_provider",
            "oauth_id",
            name="uq_users_oauth_identity",
        ),
        Index("uq_users_username_lower", text("lower(username)"), unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=True)
    oauth_provider = Column(String, nullable=True)
    oauth_id = Column(String, nullable=True)
    username = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=True)
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
    status = Column(
        Enum(
            UserStatus,
            name="user_status",
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
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
