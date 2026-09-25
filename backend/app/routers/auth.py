import logging
import time
from typing import Annotated, Any
from uuid import UUID

import httpx
from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import EmailStr, TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.oauth import GoogleClaims, get_google_oauth_client, google_username_candidates
from app.auth.security import create_access_token, hash_password, verify_password_and_update
from app.config import get_settings
from app.database import get_db
from app.models.user import User, UserRole, UserStatus
from app.schemas.common import SuccessEnvelope
from app.schemas.user import AuthData, UserLogin, UserRegister, UserResponse
from app.utils.validators import normalize_email


router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
OAUTH_HANDOFF_KEY = "google_handoff"
OAUTH_HANDOFF_MAX_AGE_SECONDS = 60
EMAIL_ADAPTER = TypeAdapter(EmailStr)
AuthResponse = SuccessEnvelope[AuthData]


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        data=AuthData(
            user=UserResponse.model_validate(user),
            token=create_access_token(user.id),
        )
    )


def _ensure_active_user(user: User) -> None:
    if user.status == UserStatus.BANNED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned")


def _oauth_redirect(destination: str) -> RedirectResponse:
    return RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)


def _oauth_exchange_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="OAuth handoff expired or invalid",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _stored_email_form(identifier: str) -> str:
    email = normalize_email(identifier)
    try:
        return str(EMAIL_ADAPTER.validate_python(email))
    except PydanticValidationError:
        return email


def _resolve_google_user(db: Session, claims: GoogleClaims) -> User:
    existing_user = db.scalar(
        select(User).where(User.oauth_provider == "google", User.oauth_id == claims.sub)
    )
    if existing_user is not None:
        _ensure_active_user(existing_user)
        return existing_user

    email = str(claims.email)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        logger.warning("google_oauth_failed reason=email_collision")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    username = next(
        (
            candidate
            for candidate in google_username_candidates(email)
            if db.scalar(
                select(User.id).where(func.lower(User.username) == candidate.lower())
            )
            is None
        ),
        None,
    )
    if username is None:
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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth unavailable",
        ) from exc


@router.post(
    "/register",
    summary="Register an account",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: UserRegister,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    email = str(payload.email)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    if db.scalar(
        select(User.id).where(func.lower(User.username) == payload.username.lower())
    ) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    user = User(
        email=email,
        username=payload.username,
        password_hash=hash_password(payload.password.get_secret_value()),
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


@router.post("/login", summary="Log in with email or username", response_model=AuthResponse)
def login(
    payload: UserLogin,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    identifier = payload.identifier
    if "@" in identifier:
        lookup = User.email == _stored_email_form(identifier)
    else:
        lookup = func.lower(User.username) == identifier.lower()
    user = db.scalar(select(User).where(lookup))
    password_is_valid, updated_hash = verify_password_and_update(
        payload.password.get_secret_value(),
        user.password_hash if user is not None else None,
    )
    if user is None or not password_is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email, username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _ensure_active_user(user)
    if updated_hash is not None:
        user.password_hash = updated_hash
        db.commit()
        db.refresh(user)
    return _auth_response(user)


@router.get("/oauth/google", summary="Start Google OAuth")
async def google_oauth_login(
    request: Request,
    google_client: Annotated[Any, Depends(get_google_client)],
) -> RedirectResponse:
    try:
        return await google_client.authorize_redirect(
            request,
            get_settings().oauth_google_redirect_uri,
        )
    except (httpx.HTTPError, RuntimeError) as exc:
        request.session.clear()
        logger.warning("google_oauth_failed error=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google OAuth unavailable",
        ) from exc


@router.get("/oauth/google/callback", summary="Complete Google OAuth")
async def google_oauth_callback(
    request: Request,
    google_client: Annotated[Any, Depends(get_google_client)],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    """Validate Google's OIDC response and create a token-free browser handoff."""

    try:
        token = await google_client.authorize_access_token(
            request,
            claims_options={"iss": {"essential": True, "values": list(GOOGLE_ISSUERS)}},
            leeway=60,
        )
        claims = GoogleClaims.model_validate(dict(token["userinfo"]))
    except Exception as exc:
        if isinstance(exc, OAuthError) and exc.error == "access_denied":
            logger.info("google_oauth_cancelled")
            return _oauth_redirect("/login?oauth=cancelled")
        logger.warning("google_oauth_failed error=%s", type(exc).__name__)
        return _oauth_redirect("/login?oauth=failed")
    finally:
        request.session.clear()

    try:
        user = _resolve_google_user(db, claims)
    except HTTPException:
        return _oauth_redirect("/login?oauth=failed")

    request.session[OAUTH_HANDOFF_KEY] = {
        "user_id": str(user.id),
        "expires_at": time.time() + OAUTH_HANDOFF_MAX_AGE_SECONDS,
    }
    return _oauth_redirect("/oauth/callback")


@router.post(
    "/oauth/google/exchange",
    summary="Exchange a Google OAuth browser handoff",
    response_model=AuthResponse,
)
def exchange_google_oauth_handoff(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    """Swap the signed, short-lived handoff kept in the session cookie for a bearer token."""

    handoff = request.session.pop(OAUTH_HANDOFF_KEY, None)
    request.session.clear()
    if not isinstance(handoff, dict) or handoff.get("expires_at", 0) < time.time():
        raise _oauth_exchange_error()
    try:
        user = db.get(User, UUID(handoff["user_id"]))
    except (KeyError, TypeError, ValueError):
        raise _oauth_exchange_error() from None
    if user is None:
        raise _oauth_exchange_error()
    _ensure_active_user(user)
    return _auth_response(user)
