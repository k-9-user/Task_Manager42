from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, TypeVar

from pydantic import EmailStr, Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict, SettingsError

from app.utils.validators import (
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
    USERNAME_PATTERN,
    has_control_or_space_characters,
    has_unsafe_url_characters,
    is_safe_https_url,
    normalize_email,
    validate_username,
)


ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
DOCKER_SECRETS_DIR = Path("/run/secrets")
SettingsType = TypeVar("SettingsType", bound=BaseSettings)


class ConfigurationError(RuntimeError):
    """Safe configuration failure whose message never contains input values."""


class DatabaseSettings(BaseSettings):
    database_url: SecretStr = Field(min_length=1)

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        secrets_dir=DOCKER_SECRETS_DIR,
        extra="ignore",
    )


class Settings(DatabaseSettings):
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_expiration: int = Field(default=3600, gt=0)
    oauth_google_client_id: str = ""
    oauth_google_client_secret: SecretStr = SecretStr("")
    oauth_google_redirect_uri: str = ""
    oauth_session_secret: SecretStr = Field(min_length=32)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["https://localhost"]
    )
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = Field(default=10, gt=0)
    smtp_host: str = ""
    smtp_port: int = Field(default=1025, gt=0, le=65535)
    mail_from: str = "no-reply@taskmanager.local"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value

        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS must contain at least one origin")
        return origins

    @field_validator("oauth_google_redirect_uri")
    @classmethod
    def validate_google_redirect_uri(cls, value: str) -> str:
        redirect_uri = value.strip()
        if not redirect_uri:
            return redirect_uri

        if has_unsafe_url_characters(redirect_uri) or not is_safe_https_url(
            redirect_uri,
            allow_fragment=False,
        ):
            raise ValueError("OAUTH_GOOGLE_REDIRECT_URI must be an HTTPS URL")
        return redirect_uri

    @field_validator("jwt_secret", "oauth_session_secret")
    @classmethod
    def validate_signing_secret(
        cls,
        value: SecretStr,
    ) -> SecretStr:
        secret = value.get_secret_value()
        placeholders = {
            "replace_with_a_random_32_plus_character_secret",
            "replace_with_a_random_32_plus_character_jwt_secret",
            "replace_with_a_random_32_plus_character_oauth_secret",
        }
        if (
            secret in placeholders
            or not secret.isascii()
            or has_control_or_space_characters(secret)
        ):
            raise ValueError("signing secrets must be randomly generated")
        return value

    @model_validator(mode="after")
    def require_distinct_signing_secrets(self) -> "Settings":
        if (
            self.jwt_secret.get_secret_value()
            == self.oauth_session_secret.get_secret_value()
        ):
            raise ValueError("JWT and OAuth session secrets must be distinct")
        return self

    @model_validator(mode="after")
    def require_paired_google_credentials(self) -> "Settings":
        client_secret = self.oauth_google_client_secret.get_secret_value()
        if bool(self.oauth_google_client_id) != bool(client_secret):
            raise ValueError(
                "OAUTH_GOOGLE_CLIENT_ID and oauth_google_client_secret "
                "must both be set or both be empty"
            )
        return self


class BootstrapSettings(DatabaseSettings):
    bootstrap_admin_email: EmailStr
    bootstrap_admin_username: str = Field(
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
        pattern=USERNAME_PATTERN,
    )
    bootstrap_admin_password: SecretStr = Field(min_length=12, max_length=128)

    _email_normalizer = field_validator("bootstrap_admin_email", mode="before")(
        normalize_email
    )
    _username_validator = field_validator(
        "bootstrap_admin_username", mode="before"
    )(validate_username)

    @field_validator("bootstrap_admin_password")
    @classmethod
    def validate_admin_password(cls, value: SecretStr) -> SecretStr:
        password = value.get_secret_value()
        if any(ord(character) < 0x20 or ord(character) == 0x7F for character in password):
            raise ValueError("bootstrap admin password must contain printable characters")
        return value


def _load_settings(settings_type: type[SettingsType]) -> SettingsType:
    try:
        return settings_type()
    except ValidationError as exc:
        fields = sorted({str(error["loc"][0]) for error in exc.errors() if error["loc"]})
        model_errors = sorted({
            str(error["msg"]).removeprefix("Value error, ")
            for error in exc.errors()
            if not error["loc"]
        })
        details = fields + model_errors
        raise ConfigurationError(
            "Invalid configuration: " + ", ".join(details or ["unknown field"])
        ) from None
    except (OSError, SettingsError):
        raise ConfigurationError("Configuration secret files are unreadable") from None


@lru_cache
def get_database_settings() -> DatabaseSettings:
    return _load_settings(DatabaseSettings)


@lru_cache
def get_settings() -> Settings:
    return _load_settings(Settings)


@lru_cache
def get_bootstrap_settings() -> BootstrapSettings:
    return _load_settings(BootstrapSettings)
