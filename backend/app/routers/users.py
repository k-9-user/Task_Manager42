from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.config import Settings, get_settings
from app.database import get_db
from app.models.user import User, UserRole, UserStatus
from app.schemas.common import SimpleSuccessResponse, SuccessEnvelope
from app.schemas.user import (
    AdminUserUpdate,
    UserData,
    UserResponse,
    UserRoleUpdate,
    UserStatusUpdate,
    UserUpdate,
    UsersData,
)
from app.services.accounts import (
    ensure_another_active_admin,
    ensure_not_bootstrap_admin,
    hand_off_projects,
    lock_and_reload,
)
from app.services.uploads import remove_files
from app.utils.validators import escape_like_pattern, normalize_email


router = APIRouter(prefix="/api/users", tags=["users"])
MAX_PAGE = 1_000_000


def _user_response(user: User) -> SuccessEnvelope[UserData]:
    return SuccessEnvelope(data=UserData(user=UserResponse.model_validate(user)))


def _lock_and_revalidate_admin(db: Session, current_admin: User) -> User:
    """Serialize the admin-count invariant, then re-check the actor under it."""

    admin = lock_and_reload(db, current_admin)
    if admin.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    if admin.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned")
    return admin


def _load_target(db: Session, user_id: UUID) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return target


def _commit_username_change(db: Session, user: User) -> None:
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        ) from exc


@router.get("/me", summary="Get current user", response_model=SuccessEnvelope[UserData])
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessEnvelope[UserData]:
    return _user_response(current_user)


@router.put("/me", summary="Update current user", response_model=SuccessEnvelope[UserData])
def update_me(
    payload: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[UserData]:
    if payload.username is not None:
        if payload.username != current_user.username:
            ensure_not_bootstrap_admin(current_user)
        current_user.username = payload.username
    if payload.avatar is not None:
        current_user.avatar_url = payload.avatar
    if "display_name" in payload.model_fields_set:
        current_user.display_name = payload.display_name

    _commit_username_change(db, current_user)
    return _user_response(current_user)


@router.get(
    "/lookup",
    summary="Look up a user by exact email",
    response_model=SuccessEnvelope[UserData],
)
def lookup_user_by_email(
    email: Annotated[str, Query(min_length=1, max_length=255)],
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[UserData]:
    """Exact-match lookup so a project owner can invite someone; never a searchable directory."""

    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_response(user)


@router.get("", summary="List users", response_model=SuccessEnvelope[UsersData])
def list_users(
    _current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(max_length=255)] = None,
    role: UserRole | None = None,
    user_status: Annotated[UserStatus | None, Query(alias="status")] = None,
) -> SuccessEnvelope[UsersData]:
    filters = []
    normalized_query = q.strip() if q is not None else ""
    if normalized_query:
        search_pattern = f"%{escape_like_pattern(normalized_query)}%"
        filters.append(
            or_(
                User.username.ilike(search_pattern, escape="\\"),
                User.email.ilike(search_pattern, escape="\\"),
                User.display_name.ilike(search_pattern, escape="\\"),
            )
        )
    if role is not None:
        filters.append(User.role == role)
    if user_status is not None:
        filters.append(User.status == user_status)

    total = db.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    users = db.scalars(
        select(User)
        .where(*filters)
        .order_by(User.created_at.desc(), User.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return SuccessEnvelope(
        data=UsersData(users=[UserResponse.model_validate(user) for user in users], total=total)
    )


@router.put("/{user_id}", summary="Update a user", response_model=SuccessEnvelope[UserData])
def update_user(
    user_id: UUID,
    payload: AdminUserUpdate,
    _current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[UserData]:
    target = _load_target(db, user_id)
    if payload.username is not None:
        if payload.username != target.username:
            ensure_not_bootstrap_admin(target)
        target.username = payload.username
    if "display_name" in payload.model_fields_set:
        target.display_name = payload.display_name

    _commit_username_change(db, target)
    return _user_response(target)


@router.put(
    "/{user_id}/role",
    summary="Change a user role",
    response_model=SuccessEnvelope[UserData],
)
def update_user_role(
    user_id: UUID,
    payload: UserRoleUpdate,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[UserData]:
    _lock_and_revalidate_admin(db, current_admin)
    target = _load_target(db, user_id)
    if target.role == payload.role:
        return _user_response(target)
    ensure_not_bootstrap_admin(target)
    if payload.role != UserRole.ADMIN:
        ensure_another_active_admin(db, target, "At least one administrator is required")

    target.role = payload.role
    db.commit()
    db.refresh(target)
    return _user_response(target)


@router.put(
    "/{user_id}/status",
    summary="Change a user status",
    response_model=SuccessEnvelope[UserData],
)
def update_user_status(
    user_id: UUID,
    payload: UserStatusUpdate,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[UserData]:
    _lock_and_revalidate_admin(db, current_admin)
    target = _load_target(db, user_id)
    if target.status == payload.status:
        return _user_response(target)
    if payload.status == UserStatus.BANNED:
        ensure_not_bootstrap_admin(target)
        ensure_another_active_admin(db, target, "At least one active administrator is required")

    target.status = payload.status
    db.commit()
    db.refresh(target)
    return _user_response(target)


@router.delete("/{user_id}", summary="Delete a user", response_model=SimpleSuccessResponse)
def delete_user(
    user_id: UUID,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SimpleSuccessResponse:
    """Delete an account, handing off its projects, while preserving an administrator."""

    _lock_and_revalidate_admin(db, current_admin)
    target = _load_target(db, user_id)
    ensure_not_bootstrap_admin(target)
    ensure_another_active_admin(db, target, "At least one administrator is required")

    files = hand_off_projects(db, target.id, settings)
    db.delete(target)
    db.commit()
    remove_files(files)
    return SimpleSuccessResponse()
