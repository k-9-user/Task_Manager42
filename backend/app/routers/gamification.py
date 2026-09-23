from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.common import SuccessEnvelope
from app.schemas.gamification import GamificationData
from app.services.gamification import build_summary

router = APIRouter(prefix="/api/gamification", tags=["gamification"])


@router.get(
    "/me",
    response_model=SuccessEnvelope[GamificationData],
    summary="Current user's XP, level, badges and achievements",
)
def get_my_progress(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return SuccessEnvelope(
        data=GamificationData.model_validate(build_summary(db, current_user.id))
    )
