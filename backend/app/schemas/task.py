import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.task import TaskStatus
from app.schemas.common import StrictRequest
from app.schemas.project import ProjectMemberResponse, ProjectResponse


class TaskCreate(StrictRequest):
    """The project comes from the URL, never from the body, so a client cannot target another."""

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None


class TaskUpdate(StrictRequest):
    """Only the fields present in the body are updated."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None


class PublicTaskCreate(StrictRequest):
    """Minimal request body for the public task creation contract."""

    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def validate_title(cls, title: str) -> str:
        if not title.strip():
            raise ValueError("title must not be empty")
        return title


class PublicTaskUpdate(StrictRequest):
    """Fields that the public API is allowed to update on a task."""

    status: TaskStatus | None = None


class TaskImportRecord(StrictRequest):
    """Writable task fields plus metadata emitted by supported exports."""

    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus = TaskStatus.TODO
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None
    id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    project_name: str | None = Field(default=None, max_length=255)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def drop_empty_cells(cls, data: Any) -> Any:
        """An empty CSV cell means the field was not given, so its default applies."""

        if isinstance(data, dict):
            return {key: value for key, value in data.items() if value != ""}
        return data

    @field_validator("title")
    @classmethod
    def normalize_title(cls, title: str) -> str:
        title = title.strip()
        if not title:
            raise ValueError("title must not be empty")
        return title


class TaskSummary(BaseModel):
    """A task without its banner, as the public API, search and export return it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None = None
    status: TaskStatus
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None
    created_at: datetime
    updated_at: datetime


class TaskResponse(TaskSummary):
    banner_url: str | None = None


class TaskData(BaseModel):
    task: TaskResponse


class ProjectDetailResponse(BaseModel):
    project: ProjectResponse
    members: list[ProjectMemberResponse]
    tasks: list[TaskResponse]
