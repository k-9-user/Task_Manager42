import logging

from fastapi import HTTPException, status

from app.config import get_settings
from app.models.user import User


BOOTSTRAP_ADMIN_PROTECTED = "The bootstrap administrator is protected"

logger = logging.getLogger(__name__)


def ensure_not_bootstrap_admin(user: User) -> None:
    """Refuse a change that would stop the next start from matching BOOTSTRAP_ADMIN_*."""

    bootstrap_email = get_settings().bootstrap_admin_email
    if bootstrap_email and user.email == bootstrap_email:
        logger.warning("bootstrap_admin_change_denied target_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=BOOTSTRAP_ADMIN_PROTECTED,
        )
