import logging
import re
from base64 import urlsafe_b64encode
from collections.abc import Mapping
from functools import lru_cache
from hashlib import sha256
from typing import Any, Literal
from urllib.parse import urlsplit

from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.config import get_settings


GOOGLE_CLIENT_NAME = "google"
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)
GOOGLE_SCOPE = "openid email profile"

_GOOGLE_SETTING_NAMES = (
    "oauth_google_client_id",
    "oauth_google_client_secret",
    "oauth_google_redirect_uri",
)
_USERNAME_MAX_LENGTH = 50
_PRIMARY_USERNAME_SUFFIX_LENGTH = 16
_UNSAFE_USERNAME_CHARACTERS = re.compile(r"[^a-z0-9]+")

# Authlib 1.7 logs the PKCE verifier at DEBUG; keep that secret out of logs even
# when an operator temporarily lowers the application's global log threshold.
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

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: Any) -> Any:
        if not isinstance(value, str):
            raise ValueError("email must be a string")
        return value.strip().lower()

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
            or "\\" in picture
            or any(
                character.isspace()
                or ord(character) < 0x20
                or ord(character) == 0x7F
                for character in picture
            )
        ):
            raise ValueError("picture must be a valid HTTPS URL")

        try:
            parsed = urlsplit(picture)
            parsed_port = parsed.port
        except ValueError as exc:
            raise ValueError("picture must be a valid HTTPS URL") from exc

        if (
            parsed.scheme.lower() != "https"
            or not parsed.netloc
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed_port is not None and not 1 <= parsed_port <= 65535
        ):
            raise ValueError("picture must be a valid HTTPS URL")
        return picture


def _setting_text(settings: object, name: str) -> str:
    value = getattr(settings, name, None)
    reveal = getattr(value, "get_secret_value", None)
    if callable(reveal):
        value = reveal()
    if not isinstance(value, str):
        return ""
    return value.strip()


def is_google_oauth_configured(settings: object) -> bool:
    """Return whether all values needed for Google OAuth are present."""

    return all(_setting_text(settings, name) for name in _GOOGLE_SETTING_NAMES)


@lru_cache
def get_google_oauth_client() -> Any:
    """Return the process-wide configured Google OIDC client."""

    settings = get_settings()
    if not is_google_oauth_configured(settings):
        raise RuntimeError("Google OAuth is not configured")

    registry = OAuth()
    registry.register(
        GOOGLE_CLIENT_NAME,
        client_id=_setting_text(settings, "oauth_google_client_id"),
        client_secret=_setting_text(settings, "oauth_google_client_secret"),
        server_metadata_url=GOOGLE_DISCOVERY_URL,
        client_kwargs={
            "scope": GOOGLE_SCOPE,
            "code_challenge_method": "S256",
        },
    )
    client = registry.create_client(GOOGLE_CLIENT_NAME)
    if client is None:
        raise RuntimeError("Google OAuth client is not registered")
    return client


def validate_google_claims(claims: Mapping[str, Any]) -> GoogleClaims:
    """Validate identity fields from an Authlib-verified provider response."""

    return GoogleClaims.model_validate(dict(claims))


def google_username_candidates(email: str, sub: str) -> tuple[str, ...]:
    """Build stable username candidates without treating SHA-256 as a secret hash."""

    if not isinstance(email, str) or "@" not in email:
        raise ValueError("email must contain a local part")
    if not isinstance(sub, str) or not 1 <= len(sub) <= 255 or not sub.isascii():
        raise ValueError("sub must be between 1 and 255 ASCII characters")

    local_part = email.strip().lower().split("@", maxsplit=1)[0]
    sanitized = _UNSAFE_USERNAME_CHARACTERS.sub("_", local_part).strip("_")
    base = sanitized or "google_user"

    digest = sha256(b"google\0" + sub.encode("ascii")).digest()
    digest_hex = digest.hex()
    primary = (
        f"{base[: _USERNAME_MAX_LENGTH - _PRIMARY_USERNAME_SUFFIX_LENGTH - 1]}_"
        f"{digest_hex[:_PRIMARY_USERNAME_SUFFIX_LENGTH]}"
    )
    full_digest = urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    fallback = f"g_{full_digest}"
    return primary, fallback
