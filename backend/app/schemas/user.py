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

from app.models.user import UserRole
from app.utils.validators import (
    AVATAR_MAX_LENGTH,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
    USERNAME_PATTERN,
    normalize_email,
    validate_avatar,
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

    _username_validator = field_validator("username", mode="before")(validate_username)
    _avatar_validator = field_validator("avatar", mode="before")(validate_avatar)

    @model_validator(mode="after")
    def require_update(self) -> "UserUpdate":
        if self.username is None and self.avatar is None:
            raise ValueError("at least one profile field is required")
        return self


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    username: str
    role: UserRole
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


class UsersData(BaseModel):
    users: list[UserResponse]
    total: int = Field(ge=0)


class UsersResponse(BaseModel):
    success: Literal[True] = True
    data: UsersData


class DeleteData(BaseModel):
    success: Literal[True] = True


class DeleteResponse(BaseModel):
    success: Literal[True] = True
    data: DeleteData


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: str
