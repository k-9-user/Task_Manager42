from datetime import datetime
from typing import Literal
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

from app.models.user import UserRole, UserStatus
from app.utils.validators import (
    AVATAR_MAX_LENGTH,
    DISPLAY_NAME_MAX_LENGTH,
    STATUS_REASON_MAX_LENGTH,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
    USERNAME_PATTERN,
    normalize_email,
    validate_avatar,
    validate_display_name,
    validate_status_reason,
    validate_username,
)


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserRegister(StrictRequest):
    email: EmailStr
    username: str = Field(
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
        pattern=USERNAME_PATTERN,
    )
    password: SecretStr = Field(min_length=12, max_length=128)

    _email_normalizer = field_validator("email", mode="before")(normalize_email)
    _username_validator = field_validator("username", mode="before")(validate_username)


class UserLogin(StrictRequest):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)

    _email_normalizer = field_validator("email", mode="before")(normalize_email)


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

    _username_validator = field_validator("username", mode="before")(validate_username)
    _avatar_validator = field_validator("avatar", mode="before")(validate_avatar)
    _display_name_validator = field_validator("display_name", mode="before")(
        validate_display_name
    )

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


class AuthResponse(BaseModel):
    success: Literal[True] = True
    data: AuthData


class UserData(BaseModel):
    user: UserResponse


class CurrentUserResponse(BaseModel):
    success: Literal[True] = True
    data: UserData


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

    _username_validator = field_validator("username", mode="before")(validate_username)
    _display_name_validator = field_validator("display_name", mode="before")(
        validate_display_name
    )

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

    _reason_validator = field_validator("reason", mode="before")(
        validate_status_reason
    )


class UsersData(BaseModel):
    users: list[UserResponse]
    total: int = Field(ge=0)


class UsersResponse(BaseModel):
    success: Literal[True] = True
    data: UsersData


class DeleteData(BaseModel):
    pass


class DeleteResponse(BaseModel):
    success: Literal[True] = True
    data: DeleteData


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: str
