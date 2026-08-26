import logging
import secrets
from collections.abc import Mapping
from typing import Annotated, Any

import httpx
from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from joserfc.errors import JoseError
from pydantic import ValidationError as PydanticValidationError
from pwdlib.exceptions import UnknownHashError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.oauth import (
    create_google_oauth,
    get_google_oauth_client,
    google_username_candidates,
    is_google_oauth_configured,
    validate_google_claims,
)
from app.auth.security import (
    create_access_token,
    hash_password,
    verify_password_and_update,
    verify_password_or_dummy,
)
from app.config import get_settings
from app.database import get_db
from app.models.user import ADMIN_INVARIANT_LOCK_KEY, User, UserRole
from app.schemas.user import (
    AuthData,
    AuthResponse,
    ErrorResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

GOOGLE_ISSUERS = (
    "accounts.google.com",
    "https://accounts.google.com",
)


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        data=AuthData(
            user=UserResponse.model_validate(user),
            token=create_access_token(user.id),
        )
    )


def _lock_admin_invariants(db: Session) -> None:
    db.execute(select(func.pg_advisory_xact_lock(ADMIN_INVARIANT_LOCK_KEY)))


def _new_user_role_locked(db: Session) -> UserRole:
    first_user_id = db.scalar(select(User.id).limit(1))
    return UserRole.ADMIN if first_user_id is None else UserRole.USER


def get_google_client(request: Request) -> Any:
    settings = get_settings()
    if not is_google_oauth_configured(settings):
        request.session.clear()
        logger.warning("google_oauth_failed category=configuration")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth unavailable",
        )
    try:
        return get_google_oauth_client(create_google_oauth(settings))
    except RuntimeError as exc:
        request.session.clear()
        logger.warning("google_oauth_failed category=configuration")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth unavailable",
        ) from exc


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
    password_hash = hash_password(payload.password.get_secret_value())
    _lock_admin_invariants(db)
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
        password_hash=password_hash,
        role=_new_user_role_locked(db),
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
    password = payload.password.get_secret_value()
    updated_hash: str | None = None
    if password_hash is None:
        password_is_valid = verify_password_or_dummy(password, None)
    else:
        try:
            password_is_valid, updated_hash = verify_password_and_update(
                password,
                password_hash,
            )
        except UnknownHashError:
            password_is_valid = verify_password_or_dummy(password, password_hash)
    if user is None or not password_is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if updated_hash is not None:
        user.password_hash = updated_hash
        db.commit()
        db.refresh(user)
    return _auth_response(user)


@router.get(
    "/oauth/google",
    responses={
        status.HTTP_502_BAD_GATEWAY: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def google_oauth_login(
    request: Request,
    google_client: Annotated[Any, Depends(get_google_client)],
) -> RedirectResponse:
    settings = get_settings()
    try:
        return await google_client.authorize_redirect(
            request,
            settings.oauth_google_redirect_uri,
            state=secrets.token_urlsafe(32),
            nonce=secrets.token_urlsafe(32),
            code_verifier=secrets.token_urlsafe(64),
        )
    except (httpx.HTTPError, RuntimeError) as exc:
        request.session.clear()
        logger.warning("google_oauth_failed category=provider_discovery")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google OAuth unavailable",
        ) from exc


@router.get(
    "/oauth/google/callback",
    response_model=AuthResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_502_BAD_GATEWAY: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def google_oauth_callback(
    request: Request,
    google_client: Annotated[Any, Depends(get_google_client)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    try:
        token = await google_client.authorize_access_token(
            request,
            claims_options={
                "iss": {"essential": True, "values": list(GOOGLE_ISSUERS)}
            },
            leeway=60,
        )
        if not isinstance(token, Mapping):
            raise ValueError("Missing OAuth token response")
        userinfo = token.get("userinfo")
        if not isinstance(userinfo, Mapping):
            raise ValueError("Missing validated user information")
        claims = validate_google_claims(userinfo)
    except httpx.HTTPError as exc:
        logger.warning("google_oauth_failed category=provider_transport")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google OAuth unavailable",
        ) from exc
    except RuntimeError as exc:
        logger.warning("google_oauth_failed category=provider_metadata")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google OAuth unavailable",
        ) from exc
    except (OAuthError, JoseError, PydanticValidationError, TypeError, ValueError) as exc:
        logger.warning("google_oauth_failed category=protocol_or_claims")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth failed",
        ) from exc
    finally:
        request.session.clear()

    existing_user = db.scalar(
        select(User).where(
            User.oauth_provider == "google",
            User.oauth_id == claims.sub,
        )
    )
    if existing_user is not None:
        return _auth_response(existing_user)

    _lock_admin_invariants(db)
    existing_user = db.scalar(
        select(User).where(
            User.oauth_provider == "google",
            User.oauth_id == claims.sub,
        )
    )
    if existing_user is not None:
        return _auth_response(existing_user)

    email = str(claims.email)
    email_exists = db.scalar(
        select(User.id).where(func.lower(User.email) == email)
    )
    if email_exists is not None:
        logger.warning("google_oauth_failed category=email_collision")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    username = next(
        (
            candidate
            for candidate in google_username_candidates(email, claims.sub)
            if db.scalar(select(User.id).where(User.username == candidate)) is None
        ),
        None,
    )
    if username is None:
        logger.warning("google_oauth_failed category=username_collision")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Google account could not be created",
        )

    user = User(
        email=email,
        username=username,
        password_hash=None,
        oauth_provider="google",
        oauth_id=claims.sub,
        role=_new_user_role_locked(db),
    )
    if claims.picture is not None:
        user.avatar_url = claims.picture
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        logger.warning("google_oauth_failed category=account_integrity")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Google account could not be created",
        ) from exc
    return _auth_response(user)
