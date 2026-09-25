from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    db: Literal["ok"] = "ok"


class BackupStatusFile(BaseModel):
    """What the backup service writes after every run (backup/backup.sh)."""

    last_success_at: AwareDatetime | None
    count: int = Field(ge=0)
    interval_minutes: int = Field(gt=0)
    last_failure_at: AwareDatetime | None


class BackupStatus(BaseModel):
    state: Literal["ok", "stale", "failing", "missing"]
    last_success_at: datetime | None = None
    count: int = 0
    interval_minutes: int | None = None


class StatusResponse(BaseModel):
    status: Literal["ok", "degraded"]
    api: Literal["ok"] = "ok"
    database: Literal["ok", "down"]
    backups: BackupStatus
    checked_at: datetime
