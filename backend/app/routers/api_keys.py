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
from app.schemas.api_key import ApiKeyData, ApiKeyListData, IssuedApiKey
from app.schemas.common import SimpleSuccessResponse, SuccessEnvelope


router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


@router.post(
    "",
    response_model=SuccessEnvelope[ApiKeyData],
    status_code=status.HTTP_201_CREATED,
)
def issue_api_key(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[ApiKeyData]:
    raw_key = generate_api_key()
    api_key = ApiKey(user_id=current_user.id, key_hash=hash_api_key(raw_key))
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return SuccessEnvelope(
        data=ApiKeyData(
            api_key=IssuedApiKey(id=api_key.id, key=raw_key, created_at=api_key.created_at)
        )
    )


@router.get("", response_model=SuccessEnvelope[ApiKeyListData])
def list_api_keys(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[ApiKeyListData]:
    api_keys = db.scalars(
        select(ApiKey)
        .where(ApiKey.user_id == current_user.id)
        .order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
    ).all()
    return SuccessEnvelope(data=ApiKeyListData(api_keys=api_keys))


@router.delete("/{key_id}", response_model=SimpleSuccessResponse)
def revoke_api_key(
    key_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SimpleSuccessResponse:
    api_key = db.scalar(
        select(ApiKey)
        .where(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
        .with_for_update()
    )
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    db.delete(api_key)
    db.commit()
    return SimpleSuccessResponse()
