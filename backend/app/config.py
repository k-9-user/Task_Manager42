from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    database_url: str = Field(min_length=1)
    jwt_secret: str = Field(min_length=32)
    jwt_expiration: int = Field(default=3600, gt=0)
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
