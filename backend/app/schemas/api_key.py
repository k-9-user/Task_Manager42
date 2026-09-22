from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApiKeyMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class IssuedApiKey(ApiKeyMetadata):
    key: str


class ApiKeyData(BaseModel):
    api_key: IssuedApiKey


class ApiKeyResponse(BaseModel):
    success: Literal[True] = True
    data: ApiKeyData


class ApiKeyListData(BaseModel):
    api_keys: list[ApiKeyMetadata]


class ApiKeyListResponse(BaseModel):
    success: Literal[True] = True
    data: ApiKeyListData
