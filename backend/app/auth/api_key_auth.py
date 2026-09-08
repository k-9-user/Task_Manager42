import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.api_key import ApiKey
from app.models.user import User


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


def authenticate_api_key(raw_api_key: str | None, db: Session) -> User:
    if not raw_api_key:
        raise _api_key_authentication_error()

    api_key = db.scalar(select(ApiKey).where(ApiKey.key == raw_api_key))
    if api_key is None:
        raise _api_key_authentication_error()

    user = db.scalar(select(User).where(User.id == api_key.user_id))
    if user is None:
        raise _api_key_authentication_error()

    return user


def get_current_api_user(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> User:
    return authenticate_api_key(x_api_key, db)


def _api_key_authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "ApiKey"},
    )
