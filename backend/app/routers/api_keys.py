from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.api_key_auth import generate_api_key, hash_api_key
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.api_key import (
    ApiKeyData,
    ApiKeyListData,
    ApiKeyListResponse,
    ApiKeyResponse,
    IssuedApiKey,
)
from app.schemas.common import SimpleSuccessResponse


router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


def _issued_response(api_key: ApiKey, raw_key: str) -> ApiKeyResponse:
    return ApiKeyResponse(
        data=ApiKeyData(
            api_key=IssuedApiKey(
                id=api_key.id,
                key=raw_key,
                created_at=api_key.created_at,
            )
        )
    )


def _owned_key(db: Session, key_id: UUID, user_id: UUID) -> ApiKey:
    api_key = db.scalar(
        select(ApiKey)
        .where(ApiKey.id == key_id, ApiKey.user_id == user_id)
        .with_for_update()
    )
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    return api_key


@router.post("", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
def issue_api_key(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ApiKeyResponse:
    raw_key = generate_api_key()
    api_key = ApiKey(user_id=current_user.id, key_hash=hash_api_key(raw_key))
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return _issued_response(api_key, raw_key)


@router.get("", response_model=ApiKeyListResponse)
def list_api_keys(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ApiKeyListResponse:
    api_keys = db.scalars(
        select(ApiKey)
        .where(ApiKey.user_id == current_user.id)
        .order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
    ).all()
    return ApiKeyListResponse(data=ApiKeyListData(api_keys=api_keys))


@router.delete("/{key_id}", response_model=SimpleSuccessResponse)
def revoke_api_key(
    key_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SimpleSuccessResponse:
    api_key = _owned_key(db, key_id, current_user.id)
    db.delete(api_key)
    db.commit()
    return SimpleSuccessResponse()


@router.post("/{key_id}/rotate", response_model=ApiKeyResponse)
def rotate_api_key(
    key_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ApiKeyResponse:
    old_key = _owned_key(db, key_id, current_user.id)
    raw_key = generate_api_key()
    replacement = ApiKey(
        user_id=current_user.id,
        key_hash=hash_api_key(raw_key),
    )
    db.delete(old_key)
    db.add(replacement)
    db.commit()
    db.refresh(replacement)
    return _issued_response(replacement, raw_key)
