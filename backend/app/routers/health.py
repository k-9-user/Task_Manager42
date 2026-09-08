import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db


router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    db: Literal["ok"] = "ok"


@router.get(
    "/health",
    summary="Check application health",
    response_model=HealthResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database unavailable",
        }
    },
)
def health_check(
    db: Annotated[Session, Depends(get_db)],
) -> HealthResponse:
    """Confirm that the application can execute a database query."""

    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("health_check_failed category=database")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    return HealthResponse()
