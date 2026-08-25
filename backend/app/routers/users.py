from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    CurrentUserResponse,
    ErrorResponse,
    UserData,
    UserResponse,
    UserUpdate,
)


router = APIRouter(prefix="/api/users", tags=["users"])


def _user_response(user: User) -> CurrentUserResponse:
    return CurrentUserResponse(
        data=UserData(user=UserResponse.model_validate(user))
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    return _user_response(current_user)


@router.put(
    "/me",
    response_model=CurrentUserResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
def update_me(
    payload: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentUserResponse:
    if payload.username is not None and payload.username != current_user.username:
        username_exists = db.scalar(select(User.id).where(User.username == payload.username, User.id != current_user.id,))
        if username_exists is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )
        current_user.username = payload.username

    if payload.avatar is not None:
        current_user.avatar_url = payload.avatar

    try:
        db.commit()
        db.refresh(current_user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        ) from exc
    return _user_response(current_user)
