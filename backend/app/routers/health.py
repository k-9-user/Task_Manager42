import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db


router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


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


def get_backup_status_file() -> Path:
    return Path(get_settings().backup_status_file)


def _database_ok(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("health_check_failed category=database")
        return False
    return True


def _backup_status(path: Path, now: datetime) -> BackupStatus:
    try:
        recorded = BackupStatusFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return BackupStatus(state="missing")

    success, failure = recorded.last_success_at, recorded.last_failure_at
    if failure is not None and (success is None or failure > success):
        state = "failing"
    elif success is None:
        state = "missing"
    elif now - success > timedelta(minutes=2 * recorded.interval_minutes):
        state = "stale"
    else:
        state = "ok"
    return BackupStatus(
        state=state,
        last_success_at=success,
        count=recorded.count,
        interval_minutes=recorded.interval_minutes,
    )


@router.get("/health", summary="Check application health", response_model=HealthResponse)
def health_check(
    db: Annotated[Session, Depends(get_db)],
) -> HealthResponse:
    """Confirm that the application can execute a database query."""

    if not _database_ok(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    return HealthResponse()


@router.get(
    "/api/status",
    summary="Report component status for the status page",
    response_model=StatusResponse,
)
def component_status(
    db: Annotated[Session, Depends(get_db)],
    backup_status_file: Annotated[Path, Depends(get_backup_status_file)],
) -> StatusResponse:
    """Always 200: a failing component is reported in the body, not as an error."""

    now = datetime.now(UTC)
    database = "ok" if _database_ok(db) else "down"
    backups = _backup_status(backup_status_file, now)
    healthy = database == "ok" and backups.state == "ok"
    return StatusResponse(
        status="ok" if healthy else "degraded",
        database=database,
        backups=backups,
        checked_at=now,
    )
