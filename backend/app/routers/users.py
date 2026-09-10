import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.auth.project_permissions import lock_user_projects_for_write
from app.database import get_db
from app.models.user import User, UserRole, UserStatus
from app.schemas.user import (
    AdminUserUpdate,
    CurrentUserResponse,
    DeleteData,
    DeleteResponse,
    ErrorResponse,
    UserData,
    UserRoleUpdate,
    UserStatusUpdate,
    UserResponse,
    UserUpdate,
    UsersData,
    UsersResponse,
)
from app.utils.locks import lock_admin_invariants


router = APIRouter(prefix="/api/users", tags=["users"])
logger = logging.getLogger(__name__)
MAX_PAGE = 1_000_000


def _user_response(user: User) -> CurrentUserResponse:
    return CurrentUserResponse(
        data=UserData(user=UserResponse.model_validate(user))
    )


def _revalidate_admin(
    db: Session,
    current_admin: User,
    target_id: UUID,
) -> User:
    """Reload the actor so a stale admin role or ban cannot authorize an action."""

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
    if refreshed_admin.status != UserStatus.ACTIVE:
        logger.warning(
            "admin_action_denied actor_id=%s target_id=%s reason=actor_banned",
            actor_id,
            target_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is banned",
        )
    return refreshed_admin


def _lock_and_revalidate_admin(
    db: Session,
    current_admin: User,
    target_id: UUID,
) -> User:
    """Serialize the admin-count invariant, then re-read the actor under it."""

    lock_admin_invariants(db)
    return _revalidate_admin(db, current_admin, target_id)


def _load_target(db: Session, user_id: UUID) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return target


def _active_admin_count(db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(User).where(
            User.role == UserRole.ADMIN,
            User.status == UserStatus.ACTIVE,
        )
    ) or 0


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

    if payload.username is not None:
        current_user.username = payload.username

    if payload.avatar is not None:
        current_user.avatar_url = payload.avatar

    if "display_name" in payload.model_fields_set:
        current_user.display_name = payload.display_name

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
    page: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UsersResponse:
    """Return one bounded page of users to an administrator."""

    total = db.scalar(select(func.count()).select_from(User)) or 0
    users = db.scalars(
        select(User)
        .order_by(User.created_at.desc(), User.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return UsersResponse(
        data=UsersData(
            users=[UserResponse.model_validate(user) for user in users],
            total=total,
        )
    )


@router.put(
    "/{user_id}",
    summary="Update a user",
    response_model=CurrentUserResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
def update_user(
    user_id: UUID,
    payload: AdminUserUpdate,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentUserResponse:
    """Update another account's public identity as a global administrator."""

    current_admin = _revalidate_admin(db, current_admin, user_id)
    target = _load_target(db, user_id)

    if payload.username is not None:
        target.username = payload.username
    if "display_name" in payload.model_fields_set:
        target.display_name = payload.display_name

    try:
        db.commit()
        db.refresh(target)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        ) from exc
    logger.info(
        "admin_user_updated actor_id=%s target_id=%s",
        current_admin.id,
        target.id,
    )
    return _user_response(target)


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

    current_admin = _lock_and_revalidate_admin(db, current_admin, user_id)
    target = _load_target(db, user_id)
    actor_id = current_admin.id
    target_id = target.id

    if target.role == payload.role:
        return _user_response(target)

    if (
        target.role == UserRole.ADMIN
        and target.status == UserStatus.ACTIVE
        and payload.role != UserRole.ADMIN
    ):
        admin_count = _active_admin_count(db)
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


@router.put(
    "/{user_id}/status",
    summary="Change a user status",
    response_model=CurrentUserResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
def update_user_status(
    user_id: UUID,
    payload: UserStatusUpdate,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentUserResponse:
    """Ban or restore an account while preserving an active administrator."""

    current_admin = _lock_and_revalidate_admin(db, current_admin, user_id)
    target = _load_target(db, user_id)
    if target.status == payload.status:
        return _user_response(target)

    if (
        target.role == UserRole.ADMIN
        and target.status == UserStatus.ACTIVE
        and payload.status == UserStatus.BANNED
        and _active_admin_count(db) <= 1
    ):
        logger.warning(
            "admin_status_change_denied actor_id=%s target_id=%s reason=last_active_admin",
            current_admin.id,
            target.id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="At least one active administrator is required",
        )

    target.status = payload.status
    db.commit()
    db.refresh(target)
    logger.info(
        "admin_user_status_changed actor_id=%s target_id=%s status=%s reason=%r",
        current_admin.id,
        target.id,
        target.status.value,
        payload.reason,
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

    current_admin = _lock_and_revalidate_admin(db, current_admin, user_id)
    target = _load_target(db, user_id)
    actor_id = current_admin.id
    target_id = target.id

    if target.role == UserRole.ADMIN and target.status == UserStatus.ACTIVE:
        admin_count = _active_admin_count(db)
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

    lock_user_projects_for_write(db, target_id)
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
