from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
        default_factory=lambda: ["http://localhost:5173"]
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

        if "\\" in redirect_uri or any(
            character.isspace()
            or ord(character) < 0x20
            or ord(character) == 0x7F
            for character in redirect_uri
        ):
            raise ValueError("OAUTH_GOOGLE_REDIRECT_URI must be an HTTPS URL")

        try:
            parsed = urlsplit(redirect_uri)
            parsed_port = parsed.port
        except ValueError as exc:
            raise ValueError(
                "OAUTH_GOOGLE_REDIRECT_URI must be an HTTPS URL"
            ) from exc
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or parsed_port is not None and not 1 <= parsed_port <= 65_535
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
            or any(
                character.isspace()
                or ord(character) < 0x20
                or ord(character) == 0x7F
                for character in secret
            )
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
