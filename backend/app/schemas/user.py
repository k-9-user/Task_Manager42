from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.config import get_settings
from app.models.user import UserRole, UserStatus
from app.schemas.common import StrictRequest
from app.utils.validators import (
    AVATAR_MAX_LENGTH,
    DISPLAY_NAME_MAX_LENGTH,
    STATUS_REASON_MAX_LENGTH,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
    USERNAME_PATTERN,
    clean_text,
    has_control_characters,
    normalize_email,
    strip_text,
    validate_avatar,
)


def _document_password_limits(schema: dict[str, Any]) -> None:
    settings = get_settings()
    schema["minLength"] = settings.password_min_length
    schema["maxLength"] = settings.password_max_length


class UserRegister(StrictRequest):
    email: EmailStr
    username: str = Field(
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
        pattern=USERNAME_PATTERN,
    )
    password: SecretStr = Field(json_schema_extra=_document_password_limits)

    _email_normalizer = field_validator("email", mode="before")(normalize_email)
    _username_validator = field_validator("username", mode="before")(strip_text)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        password = value.get_secret_value()
        if has_control_characters(password):
            raise ValueError("password must contain visible characters only")
        settings = get_settings()
        if len(password) < settings.password_min_length:
            raise ValueError("password is too short")
        if len(password) > settings.password_max_length:
            raise ValueError("password is too long")
        return value


class UserLogin(StrictRequest):
    identifier: str = Field(min_length=1, max_length=254)
    password: SecretStr = Field(min_length=1)

    _identifier_validator = field_validator("identifier", mode="before")(strip_text)


class UserUpdate(StrictRequest):
    username: str | None = Field(
        default=None,
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
        pattern=USERNAME_PATTERN,
    )
    avatar: str | None = Field(
        default=None,
        min_length=1,
        max_length=AVATAR_MAX_LENGTH,
    )
    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=DISPLAY_NAME_MAX_LENGTH,
    )

    _username_validator = field_validator("username", mode="before")(strip_text)
    _avatar_validator = field_validator("avatar", mode="before")(validate_avatar)
    _display_name_validator = field_validator("display_name", mode="before")(clean_text)

    @model_validator(mode="after")
    def require_update(self) -> "UserUpdate":
        if (
            self.username is None
            and self.avatar is None
            and "display_name" not in self.model_fields_set
        ):
            raise ValueError("at least one profile field is required")
        return self


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    username: str
    display_name: str | None
    role: UserRole
    status: UserStatus
    avatar_url: str
    created_at: datetime
    updated_at: datetime


class AuthData(BaseModel):
    user: UserResponse
    token: str


class UserData(BaseModel):
    user: UserResponse


class UserRoleUpdate(StrictRequest):
    role: UserRole


class AdminUserUpdate(StrictRequest):
    username: str | None = Field(
        default=None,
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
        pattern=USERNAME_PATTERN,
    )
    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=DISPLAY_NAME_MAX_LENGTH,
    )

    _username_validator = field_validator("username", mode="before")(strip_text)
    _display_name_validator = field_validator("display_name", mode="before")(clean_text)

    @model_validator(mode="after")
    def require_update(self) -> "AdminUserUpdate":
        if self.username is None and "display_name" not in self.model_fields_set:
            raise ValueError("at least one user field is required")
        return self


class UserStatusUpdate(StrictRequest):
    status: UserStatus
    reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=STATUS_REASON_MAX_LENGTH,
    )

    _reason_validator = field_validator("reason", mode="before")(clean_text)


class GDPRDeleteRequest(StrictRequest):
    confirm: bool
    confirm_username: str


class UsersData(BaseModel):
    users: list[UserResponse]
    total: int = Field(ge=0)

