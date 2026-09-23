import logging
import sys

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password_and_update
from app.config import BootstrapSettings, ConfigurationError, get_bootstrap_settings
from app.database import SessionLocal
from app.models.user import User, UserRole, UserStatus
from app.utils.locks import lock_admin_invariants


logger = logging.getLogger(__name__)
INCOMPATIBLE_DATABASE = (
    "Existing database does not match configured bootstrap administrator; "
    "restore matching credentials or explicitly run make reset-db"
)


class BootstrapError(RuntimeError):
    """Safe bootstrap failure containing no credential material."""


def bootstrap_admin(db: Session, settings: BootstrapSettings) -> User:
    """Create the first administrator, or verify the exact existing first account."""

    lock_admin_invariants(db)
    first_user = db.scalar(
        select(User).order_by(User.created_at.asc(), User.id.asc()).limit(1)
    )
    password = settings.bootstrap_admin_password.get_secret_value()

    if first_user is None:
        admin = User(
            email=str(settings.bootstrap_admin_email),
            username=settings.bootstrap_admin_username,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        db.add(admin)
        try:
            db.commit()
            db.refresh(admin)
        except SQLAlchemyError:
            db.rollback()
            raise BootstrapError("Administrator bootstrap could not be completed") from None
        logger.info("bootstrap_admin_created user_id=%s", admin.id)
        return admin

    password_matches, _updated_hash = verify_password_and_update(
        password,
        first_user.password_hash,
    )
    compatible = (
        first_user.email == str(settings.bootstrap_admin_email)
        and first_user.username == settings.bootstrap_admin_username
        and first_user.role == UserRole.ADMIN
        and first_user.status == UserStatus.ACTIVE
        and password_matches
    )
    if not compatible:
        db.rollback()
        raise BootstrapError(INCOMPATIBLE_DATABASE)

    db.commit()
    db.refresh(first_user)
    logger.info("bootstrap_admin_verified user_id=%s", first_user.id)
    return first_user


def main() -> int:
    try:
        settings = get_bootstrap_settings()
        with SessionLocal() as db:
            bootstrap_admin(db, settings)
    except ConfigurationError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except BootstrapError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("Error: administrator bootstrap database operation failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
