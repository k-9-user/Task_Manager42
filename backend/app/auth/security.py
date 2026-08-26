from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from argon2 import Type
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher

from app.config import get_settings

ALGORITHM = "HS256"

_password_hash = PasswordHash(
    (
        Argon2Hasher(
            memory_cost=65_536,
            time_cost=3,
            parallelism=4,
            salt_len=16,
            hash_len=32,
            type=Type.ID,
        ),
    )
)
_dummy_password_hash = _password_hash.hash("dummy-password-equalizer")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def verify_password_and_update(
    password: str, password_hash: str
) -> tuple[bool, str | None]:
    return _password_hash.verify_and_update(password, password_hash)


def verify_password_or_dummy(password: str, password_hash: str | None) -> bool:
    candidate_hash = password_hash or _dummy_password_hash
    try:
        is_valid = verify_password(password, candidate_hash)
    except UnknownHashError:
        verify_password(password, _dummy_password_hash)
        return False
    return bool(password_hash) and is_valid


def create_access_token(
    subject: UUID | str,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    user_id = UUID(str(subject))
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + (
        expires_delta
        if expires_delta is not None
        else timedelta(seconds=get_settings().jwt_expiration)
    )
    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        get_settings().jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
        subject = payload["sub"]
        if not isinstance(subject, str):
            raise InvalidTokenError("Invalid subject")
        return str(UUID(subject))
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Invalid subject") from exc
