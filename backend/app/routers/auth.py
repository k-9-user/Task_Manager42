import hashlib
import logging
import secrets
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import httpx
from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from joserfc.errors import JoseError
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.oauth import (
    GoogleClaims,
    get_google_oauth_client,
    google_username_candidates,
    validate_google_claims,
)
from app.auth.security import (
    create_access_token,
    hash_password,
    verify_password_and_update,
)
from app.config import get_settings
from app.database import get_db
from app.models.user import User, UserRole, UserStatus
from app.models.oauth_handoff import OAuthHandoff
from app.schemas.user import (
    AuthData,
    AuthResponse,
    ErrorResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.utils.locks import lock_admin_invariants


router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

GOOGLE_ISSUERS = (
    "accounts.google.com",
    "https://accounts.google.com",
)
OAUTH_HANDOFF_KEY = "google_handoff"
OAUTH_HANDOFF_MAX_AGE_SECONDS = 60


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        data=AuthData(
            user=UserResponse.model_validate(user),
            token=create_access_token(user.id),
        )
    )


def _ensure_active_user(user: User) -> None:
    if user.status == UserStatus.BANNED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is banned",
        )


def _oauth_redirect(destination: str) -> RedirectResponse:
    return RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)


def _oauth_exchange_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="OAuth handoff expired or invalid",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _hash_oauth_handoff(raw_handoff: str) -> str:
    return hashlib.sha256(raw_handoff.encode("utf-8")).hexdigest()


def _resolve_google_user(db: Session, claims: GoogleClaims) -> User:
    existing_user = db.scalar(
        select(User).where(
            User.oauth_provider == "google",
            User.oauth_id == claims.sub,
        )
    )
    if existing_user is not None:
        _ensure_active_user(existing_user)
        return existing_user

    lock_admin_invariants(db)
    existing_user = db.scalar(
        select(User).where(
            User.oauth_provider == "google",
            User.oauth_id == claims.sub,
        )
    )
    if existing_user is not None:
        _ensure_active_user(existing_user)
        return existing_user

    email = str(claims.email)
    email_exists = db.scalar(select(User.id).where(User.email == email))
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
            if db.scalar(
                select(User.id).where(func.lower(User.username) == candidate.lower())
            )
            is None
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
        role=UserRole.USER,
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
    return user


def get_google_client(request: Request) -> Any:
    """Resolve the configured Google client or return a stable 503 response."""

    try:
        return get_google_oauth_client()
    except RuntimeError as exc:
        request.session.clear()
        logger.warning("google_oauth_failed category=configuration")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth unavailable",
        ) from exc


@router.post(
    "/register",
    summary="Register an account",
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
    """Create a local account and issue its bearer token."""

    email = str(payload.email)
    password_hash = hash_password(payload.password.get_secret_value())
    email_exists = db.scalar(select(User.id).where(User.email == email))
    if email_exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    username_exists = db.scalar(
        select(User.id).where(func.lower(User.username) == payload.username.lower())
    )
    if username_exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    user = User(
        email=email,
        username=payload.username,
        password_hash=password_hash,
        role=UserRole.USER,
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
    summary="Log in with email",
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
    """Verify local credentials and issue a bearer token."""

    email = str(payload.email)
    user = db.scalar(select(User).where(User.email == email))
    password = payload.password.get_secret_value()
    password_is_valid, updated_hash = verify_password_and_update(
        password,
        user.password_hash if user is not None else None,
    )
    if user is None or not password_is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _ensure_active_user(user)
    if updated_hash is not None:
        user.password_hash = updated_hash
        db.commit()
        db.refresh(user)
    return _auth_response(user)


@router.get(
    "/oauth/google",
    summary="Start Google OAuth",
    responses={
        status.HTTP_502_BAD_GATEWAY: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def google_oauth_login(
    request: Request,
    google_client: Annotated[Any, Depends(get_google_client)],
) -> RedirectResponse:
    """Redirect the browser into Google's secured OIDC authorization flow."""

    settings = get_settings()
    try:
        return await google_client.authorize_redirect(
            request,
            settings.oauth_google_redirect_uri,
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
    summary="Complete Google OAuth",
    responses={
        status.HTTP_303_SEE_OTHER: {
            "description": "Redirect to the frontend OAuth completion route",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def google_oauth_callback(
    request: Request,
    google_client: Annotated[Any, Depends(get_google_client)],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    """Validate Google's OIDC response and create a token-free browser handoff."""

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
    except OAuthError as exc:
        if exc.error == "access_denied":
            logger.info("google_oauth_cancelled")
            return _oauth_redirect("/login?oauth=cancelled")
        logger.warning("google_oauth_failed category=protocol_or_claims")
        return _oauth_redirect("/login?oauth=failed")
    except httpx.HTTPError:
        logger.warning("google_oauth_failed category=provider_transport")
        return _oauth_redirect("/login?oauth=failed")
    except RuntimeError:
        logger.warning("google_oauth_failed category=provider_metadata")
        return _oauth_redirect("/login?oauth=failed")
    except (
        JoseError,
        PydanticValidationError,
        TypeError,
        ValueError,
    ):
        logger.warning("google_oauth_failed category=protocol_or_claims")
        return _oauth_redirect("/login?oauth=failed")
    finally:
        request.session.clear()

    try:
        user = _resolve_google_user(db, claims)
    except HTTPException:
        return _oauth_redirect("/login?oauth=failed")

    raw_handoff = secrets.token_urlsafe(32)
    db.execute(delete(OAuthHandoff).where(OAuthHandoff.expires_at < func.now()))
    db.add(OAuthHandoff(
        user_id=user.id,
        token_hash=_hash_oauth_handoff(raw_handoff),
        expires_at=datetime.now(timezone.utc) + timedelta(
            seconds=OAUTH_HANDOFF_MAX_AGE_SECONDS
        ),
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("google_oauth_failed category=handoff_integrity")
        return _oauth_redirect("/login?oauth=failed")
    request.session[OAUTH_HANDOFF_KEY] = raw_handoff
    return _oauth_redirect("/oauth/callback")


@router.post(
    "/oauth/google/exchange",
    summary="Exchange a Google OAuth browser handoff",
    response_model=AuthResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    },
)
def exchange_google_oauth_handoff(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    handoff = request.session.pop(OAUTH_HANDOFF_KEY, None)
    request.session.clear()
    if not isinstance(handoff, str) or not handoff:
        raise _oauth_exchange_error()
    user_id = db.execute(
        delete(OAuthHandoff)
        .where(
            OAuthHandoff.token_hash == _hash_oauth_handoff(handoff),
            OAuthHandoff.expires_at >= func.now(),
        )
        .returning(OAuthHandoff.user_id)
    ).scalar_one_or_none()
    db.commit()
    if user_id is None:
        raise _oauth_exchange_error()

    user = db.get(User, user_id)
    if user is None:
        raise _oauth_exchange_error()
    _ensure_active_user(user)
    return _auth_response(user)
