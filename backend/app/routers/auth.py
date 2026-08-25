from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import (
    create_access_token,
    hash_password,
    verify_password_or_dummy,
)
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import (
    AuthData,
    AuthResponse,
    ErrorResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        data=AuthData(
            user=UserResponse.model_validate(user),
            token=create_access_token(user.id),
        )
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
def register(
    payload: UserRegister,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    email = str(payload.email)
    email_exists = db.scalar(select(User.id).where(func.lower(User.email) == email))
    if email_exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    username_exists = db.scalar(select(User.id).where(User.username == payload.username))
    if username_exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    user = User(
        email=email,
        username=payload.username,
        password_hash=hash_password(payload.password.get_secret_value()),
        role=UserRole.USER,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username already exists",
        ) from exc
    return _auth_response(user)


@router.post(
    "/login",
    response_model=AuthResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
def login(
    payload: UserLogin,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    email = str(payload.email)
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    password_hash = user.password_hash if user is not None else None
    password_is_valid = verify_password_or_dummy(
        payload.password.get_secret_value(),
        password_hash,
    )
    if user is None or not password_is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _auth_response(user)
