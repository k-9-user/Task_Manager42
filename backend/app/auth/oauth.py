import logging
import re
from collections.abc import Iterator
from functools import lru_cache
from typing import Any, Literal

from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.config import get_settings
from app.utils.validators import (
    USERNAME_MAX_LENGTH,
    has_unsafe_url_characters,
    is_safe_https_url,
    normalize_email,
)


GOOGLE_CLIENT_NAME = "google"
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)
GOOGLE_SCOPE = "openid email profile"
_ALLOWED_USERNAME_CHARACTER = re.compile(r"[a-z0-9._-]")
_UNSAFE_USERNAME_CHARACTERS = re.compile(r"[^a-z0-9._-]+")


logging.getLogger("authlib.integrations.base_client.sync_app").setLevel(
    logging.WARNING
)


class GoogleClaims(BaseModel):
    """Identity fields consumed after Authlib verifies Google's OIDC response."""

    model_config = ConfigDict(extra="ignore")

    sub: str = Field(min_length=1, max_length=255)
    email: EmailStr
    email_verified: Literal[True]
    picture: str | None = Field(default=None, max_length=2048)

    @field_validator("sub", mode="before")
    @classmethod
    def validate_subject(cls, value: Any) -> Any:
        if not isinstance(value, str) or not value.isascii():
            raise ValueError("sub must be an ASCII string")
        return value

    _email_normalizer = field_validator("email", mode="before")(normalize_email)

    @field_validator("email_verified", mode="before")
    @classmethod
    def require_verified_email(cls, value: Any) -> Any:
        if value is not True:
            raise ValueError("email_verified must be true")
        return value

    @field_validator("picture", mode="before")
    @classmethod
    def validate_picture(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("picture must be a string")

        picture = value.strip()
        if (
            not picture
            or has_unsafe_url_characters(picture)
            or not is_safe_https_url(picture)
        ):
            raise ValueError("picture must be a valid HTTPS URL")
        return picture


@lru_cache
def get_google_oauth_client() -> Any:
    """Return the process-wide configured Google OIDC client."""

    settings = get_settings()
    client_id = settings.oauth_google_client_id.strip()
    client_secret = settings.oauth_google_client_secret.get_secret_value().strip()
    if not (client_id and client_secret and settings.oauth_google_redirect_uri):
        raise RuntimeError("Google OAuth is not configured")

    registry = OAuth()
    registry.register(
        GOOGLE_CLIENT_NAME,
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url=GOOGLE_DISCOVERY_URL,
        client_kwargs={"scope": GOOGLE_SCOPE, "code_challenge_method": "S256"},
    )
    return registry.create_client(GOOGLE_CLIENT_NAME)


def google_username_candidates(email: str) -> Iterator[str]:
    """Yield readable, bounded username candidates from a Google email."""

    if not isinstance(email, str) or "@" not in email:
        raise ValueError("email must contain a local part")

    local_part = email.strip().lower().split("@", maxsplit=1)[0]
    sanitized = _UNSAFE_USERNAME_CHARACTERS.sub("_", local_part)
    if not _ALLOWED_USERNAME_CHARACTER.search(local_part):
        sanitized = ""
    base = (sanitized or "google_user")[:USERNAME_MAX_LENGTH]
    yield base

    suffix_number = 2
    while True:
        suffix = f"_{suffix_number}"
        if len(suffix) >= USERNAME_MAX_LENGTH:
            return
        yield f"{base[:USERNAME_MAX_LENGTH - len(suffix)]}{suffix}"
        suffix_number += 1
