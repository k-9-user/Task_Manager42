from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.utils.validators import (
    has_control_or_space_characters,
    has_unsafe_url_characters,
    is_safe_https_url,
)


ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    database_url: str = Field(min_length=1)
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_expiration: int = Field(default=3600, gt=0)
    oauth_google_client_id: str = ""
    oauth_google_client_secret: SecretStr = SecretStr("")
    oauth_google_redirect_uri: str = ""
    oauth_session_secret: SecretStr = Field(min_length=32)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["https://localhost:8443"]
    )
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = Field(default=10, gt=0)

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
