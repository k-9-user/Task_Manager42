import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.user import ADMIN_INVARIANT_LOCK_KEY, User, UserRole
from app.schemas.user import (
    CurrentUserResponse,
    DeleteData,
    DeleteResponse,
    ErrorResponse,
    UserData,
    UserRoleUpdate,
    UserResponse,
    UserUpdate,
    UsersData,
    UsersResponse,
)


router = APIRouter(prefix="/api/users", tags=["users"])
logger = logging.getLogger(__name__)
POSTGRESQL_MAX_BIGINT = 2**63 - 1


def _user_response(user: User) -> CurrentUserResponse:
    return CurrentUserResponse(
        data=UserData(user=UserResponse.model_validate(user))
    )


def _revalidate_admin_locked(
    db: Session,
    current_admin: User,
    target_id: UUID,
) -> User:
    """Reload the actor after locking so stale admin authority cannot be used."""

    actor_id = current_admin.id
    refreshed_admin = db.scalar(
        select(User)
        .where(User.id == actor_id)
        .execution_options(populate_existing=True)
    )
    if refreshed_admin is None:
        logger.warning(
            "admin_action_denied actor_id=%s target_id=%s reason=actor_deleted",
            actor_id,
            target_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if refreshed_admin.role != UserRole.ADMIN:
        logger.warning(
            "admin_action_denied actor_id=%s target_id=%s reason=actor_demoted",
            actor_id,
            target_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return refreshed_admin


@router.get(
    "/me",
    summary="Get current user",
    response_model=CurrentUserResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    """Return the profile associated with the bearer token."""

    return _user_response(current_user)


@router.put(
    "/me",
    summary="Update current user",
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
    """Update the current user's public profile fields."""

    if payload.username is not None and payload.username != current_user.username:
        username_exists = db.scalar(
            select(User.id).where(
                User.username == payload.username,
                User.id != current_user.id,
            )
        )
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


@router.get(
    "",
    summary="List users",
    response_model=UsersResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
def list_users(
    _current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UsersResponse:
    """Return one bounded page of users to an administrator."""

    total = db.scalar(select(func.count()).select_from(User)) or 0
    offset = (page - 1) * limit
    if offset > POSTGRESQL_MAX_BIGINT:
        users = []
    else:
        users = db.scalars(
            select(User)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    return UsersResponse(
        data=UsersData(
            users=[UserResponse.model_validate(user) for user in users],
            total=total,
        )
    )


@router.put(
    "/{user_id}/role",
    summary="Change a user role",
    response_model=CurrentUserResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
def update_user_role(
    user_id: UUID,
    payload: UserRoleUpdate,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentUserResponse:
    """Change an app-wide role while preserving at least one administrator."""

    db.execute(select(func.pg_advisory_xact_lock(ADMIN_INVARIANT_LOCK_KEY)))
    current_admin = _revalidate_admin_locked(db, current_admin, user_id)
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    actor_id = current_admin.id
    target_id = target.id

    if target.role == payload.role:
        return _user_response(target)

    if target.role == UserRole.ADMIN and payload.role != UserRole.ADMIN:
        admin_count = db.scalar(
            select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)
        ) or 0
        if admin_count <= 1:
            logger.warning(
                "admin_role_change_denied actor_id=%s target_id=%s reason=last_admin",
                actor_id,
                target_id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="At least one administrator is required",
            )

    target.role = payload.role
    db.commit()
    db.refresh(target)
    logger.info(
        "admin_role_changed actor_id=%s target_id=%s role=%s",
        actor_id,
        target_id,
        target.role.value,
    )
    return _user_response(target)


@router.delete(
    "/{user_id}",
    summary="Delete a user",
    response_model=DeleteResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
def delete_user(
    user_id: UUID,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> DeleteResponse:
    """Delete an account while preserving at least one administrator."""

    db.execute(select(func.pg_advisory_xact_lock(ADMIN_INVARIANT_LOCK_KEY)))
    current_admin = _revalidate_admin_locked(db, current_admin, user_id)
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    actor_id = current_admin.id
    target_id = target.id

    if target.role == UserRole.ADMIN:
        admin_count = db.scalar(
            select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)
        ) or 0
        if admin_count <= 1:
            logger.warning(
                "admin_delete_denied actor_id=%s target_id=%s reason=last_admin",
                actor_id,
                target_id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="At least one administrator is required",
            )

    db.delete(target)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        sqlstate = getattr(exc.orig, "sqlstate", None) or getattr(
            exc.orig,
            "pgcode",
            None,
        )
        if sqlstate == "23503":
            logger.warning(
                "admin_delete_denied actor_id=%s target_id=%s reason=dependent_data",
                actor_id,
                target_id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User has related resources",
            ) from exc
        raise

    logger.info(
        "admin_user_deleted actor_id=%s target_id=%s",
        actor_id,
        target_id,
    )
    return DeleteResponse(data=DeleteData())
