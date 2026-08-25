from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit
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


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _normalize_email(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower()
    return value


def _normalize_username(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


class UserRegister(StrictRequest):
    email: EmailStr
    username: str = Field(min_length=1, max_length=50)
    password: SecretStr = Field(min_length=12, max_length=128)

    _email_normalizer = field_validator("email", mode="before")(_normalize_email)
    _username_normalizer = field_validator("username", mode="before")(_normalize_username)


class UserLogin(StrictRequest):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)

    _email_normalizer = field_validator("email", mode="before")(_normalize_email)


class UserUpdate(StrictRequest):
    username: str | None = Field(default=None, min_length=1, max_length=50)
    avatar: str | None = Field(default=None, min_length=1, max_length=2048)

    _username_normalizer = field_validator("username", mode="before")(_normalize_username)

    @field_validator("avatar", mode="before")
    @classmethod
    def validate_avatar(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value

        avatar = value.strip()
        if not avatar or "\\" in avatar:
            raise ValueError("avatar must be a supported URL or path")

        parsed = urlsplit(avatar)
        if (
            parsed.scheme in {"http", "https"}
            and parsed.netloc
            and parsed.username is None
            and parsed.password is None
        ):
            return avatar
        if (
            not parsed.scheme
            and not parsed.netloc
            and avatar.startswith("/")
            and not avatar.startswith("//")
        ):
            return avatar
        raise ValueError("avatar must use http, https, or a root-relative path")

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


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: str
