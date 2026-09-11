"""Schémas Pydantic pour les commentaires de tâche."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    author_id: uuid.UUID
    content: str
    created_at: datetime
    updated_at: datetime


class CommentListResponse(BaseModel):
    comments: list[CommentResponse]


class CommentData(BaseModel):
    comment: CommentResponse
