from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.config import get_settings

ALGORITHM = "HS256"

_password_hash = PasswordHash.recommended()
_dummy_password_hash = _password_hash.hash("dummy-password-equalizer")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password_and_update(
    password: str,
    password_hash: str | None,
) -> tuple[bool, str | None]:
    """Verify a stored hash while equalizing absent or unsupported hashes."""

    candidate_hash = password_hash or _dummy_password_hash
    try:
        is_valid, updated_hash = _password_hash.verify_and_update(
            password,
            candidate_hash,
        )
    except UnknownHashError:
        _password_hash.verify(password, _dummy_password_hash)
        return False, None
    if not password_hash:
        return False, None
    return is_valid, updated_hash


def create_access_token(
    subject: UUID | str,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed bearer token for one user UUID."""

    settings = get_settings()
    user_id = UUID(str(subject))
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + (
        expires_delta
        if expires_delta is not None
        else timedelta(seconds=settings.jwt_expiration)
    )
    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> UUID:
    """Validate a bearer token and return its user UUID."""

    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
        subject = payload["sub"]
        if not isinstance(subject, str):
            raise InvalidTokenError("Invalid subject")
        return UUID(subject)
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Invalid subject") from exc
