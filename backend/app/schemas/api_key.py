from datetime import datetime
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


class ApiKeyListData(BaseModel):
    api_keys: list[ApiKeyMetadata]
