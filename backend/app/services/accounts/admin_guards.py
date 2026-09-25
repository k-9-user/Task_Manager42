from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.user import User, UserRole, UserStatus


ADMIN_INVARIANT_LOCK_KEY = 0x544D3432
BOOTSTRAP_ADMIN_PROTECTED = "The bootstrap administrator is protected"


def lock_admin_invariants(db: Session) -> None:
    """Serialize account bootstrap and admin-count changes until the transaction ends."""

    db.execute(select(func.pg_advisory_xact_lock(ADMIN_INVARIANT_LOCK_KEY)))


def lock_and_reload(db: Session, user: User) -> User:
    """Take the admin lock, then re-read the acting user so a stale role or ban cannot act."""

    lock_admin_invariants(db)
    fresh = db.scalar(
        select(User).where(User.id == user.id).execution_options(populate_existing=True)
    )
    if fresh is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return fresh


def ensure_another_active_admin(db: Session, user: User, detail: str) -> None:
    """Refuse a change that would leave the application without an active administrator."""

    if user.role != UserRole.ADMIN or user.status != UserStatus.ACTIVE:
        return
    active_admins = db.scalar(
        select(func.count()).select_from(User).where(
            User.role == UserRole.ADMIN,
            User.status == UserStatus.ACTIVE,
        )
    )
    if active_admins <= 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def ensure_not_bootstrap_admin(user: User) -> None:
    """Refuse a change that would stop the next start from matching BOOTSTRAP_ADMIN_*."""

    bootstrap_email = get_settings().bootstrap_admin_email
    if bootstrap_email and user.email == bootstrap_email:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=BOOTSTRAP_ADMIN_PROTECTED)
