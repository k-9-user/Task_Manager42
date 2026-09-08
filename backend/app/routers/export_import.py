import csv
import io
import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task, TaskStatus
from app.models.user import User


router = APIRouter(tags=["Export / Import"])

CSV_COLUMNS = (
    "project_id",
    "project_name",
    "task_id",
    "title",
    "description",
    "status",
    "assignee_id",
    "due_date",
    "created_at",
    "updated_at",
)
SUPPORTED_EXPORT_FORMATS = frozenset({"json", "csv"})
SUPPORTED_IMPORT_MIME_TYPES = {
    ".json": frozenset({"application/json"}),
    ".csv": frozenset(
        {
            "application/csv",
            "application/vnd.ms-excel",
            "text/csv",
        }
    ),
}
MAX_IMPORT_SIZE_BYTES = 5 * 1024 * 1024
MAX_IMPORT_RECORDS = 1000


def get_export_import_current_user() -> User:
    """Fail closed until the shared JWT current-user dependency is available."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Shared current-user authentication is not available",
    )


DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_export_import_current_user)]


@router.get(
    "/api/export",
    summary="Export visible projects and tasks",
    description=(
        "Download visible project and task data as deterministic JSON or flat CSV. "
        "Only projects owned by or shared with the authenticated user are exported."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Unsupported export format."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Shared current-user authentication is not integrated."
        },
    },
)
def export_data(
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    export_format: Annotated[
        str,
        Query(alias="format", description="Download format: json or csv."),
    ],
) -> Response:
    if export_format not in SUPPORTED_EXPORT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export format must be json or csv",
        )

    projects, tasks_by_project = _load_visible_export_data(db, current_user.id)
    if export_format == "json":
        content = json.dumps(
            {
                "projects": [
                    _serialize_project_with_tasks(
                        project,
                        tasks_by_project.get(project.id, []),
                    )
                    for project in projects
                ]
            },
            ensure_ascii=False,
            indent=2,
        )
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="task-export.json"'
            },
        )

    content = _serialize_csv(projects, tasks_by_project)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="task-export.csv"'},
    )


@router.post(
    "/api/import",
    summary="Import tasks into existing projects",
    description=(
        "Import JSON or CSV task data into existing writable projects. The entire "
        "file is validated before all tasks are committed in one transaction."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Malformed or invalid import data."
        },
        status.HTTP_403_FORBIDDEN: {"description": "Read-only project access."},
        status.HTTP_404_NOT_FOUND: {
            "description": "Target project not found or not visible."
        },
        413: {"description": "Import file exceeds the local safety limit."},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {
            "description": "Import file must be JSON or CSV."
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Shared current-user authentication is not integrated."
        },
    },
)
async def import_data(
    file: Annotated[
        UploadFile,
        File(description="JSON or CSV task export to import."),
    ],
    db: DatabaseSession,
    current_user: AuthenticatedUser,
) -> dict[str, Any]:
    import_format = _validate_import_file(file)
    raw_content = await _read_import_file(file)
    records = _parse_import_records(raw_content, import_format)

    try:
        project_cache: dict[UUID, Project] = {}
        validated_tasks = [
            _build_imported_task(db, record, current_user.id, project_cache)
            for record in records
        ]
        db.add_all(validated_tasks)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "success": True,
        "data": {"imported_count": len(validated_tasks)},
    }


def _load_visible_export_data(
    db: Session,
    user_id: UUID,
) -> tuple[list[Project], dict[UUID, list[Task]]]:
    projects = list(
        db.scalars(
            select(Project)
            .where(_project_access_filter(user_id))
            .order_by(Project.created_at.asc(), Project.id.asc())
        ).all()
    )
    tasks_by_project: dict[UUID, list[Task]] = {project.id: [] for project in projects}
    if not projects:
        return projects, tasks_by_project

    tasks = db.scalars(
        select(Task)
        .where(Task.project_id.in_(tasks_by_project))
        .order_by(Task.project_id.asc(), Task.created_at.asc(), Task.id.asc())
    ).all()
    for task in tasks:
        tasks_by_project[task.project_id].append(task)
    return projects, tasks_by_project


def _project_access_filter(user_id: UUID):
    member_project_ids = select(ProjectMember.project_id).where(
        ProjectMember.user_id == user_id
    )
    return or_(
        Project.owner_id == user_id,
        Project.id.in_(member_project_ids),
    )


def _serialize_project_with_tasks(
    project: Project,
    tasks: list[Task],
) -> dict[str, Any]:
    return {
        "id": _serialize_value(project.id),
        "name": project.name,
        "description": project.description,
        "owner_id": _serialize_value(project.owner_id),
        "created_at": _serialize_value(project.created_at),
        "tasks": [_serialize_task(task) for task in tasks],
    }


def _serialize_task(task: Task) -> dict[str, Any]:
    return {
        "id": _serialize_value(task.id),
        "project_id": _serialize_value(task.project_id),
        "title": task.title,
        "description": task.description,
        "status": _serialize_value(task.status),
        "assignee_id": _serialize_value(task.assignee_id),
        "due_date": _serialize_value(task.due_date),
        "created_at": _serialize_value(task.created_at),
        "updated_at": _serialize_value(task.updated_at),
    }


def _serialize_csv(
    projects: list[Project],
    tasks_by_project: dict[UUID, list[Task]],
) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for project in projects:
        for task in tasks_by_project.get(project.id, []):
            writer.writerow(
                {
                    "project_id": _serialize_value(project.id),
                    "project_name": project.name,
                    "task_id": _serialize_value(task.id),
                    "title": task.title,
                    "description": task.description or "",
                    "status": _serialize_value(task.status),
                    "assignee_id": _serialize_value(task.assignee_id) or "",
                    "due_date": _serialize_value(task.due_date) or "",
                    "created_at": _serialize_value(task.created_at),
                    "updated_at": _serialize_value(task.updated_at),
                }
            )
    return output.getvalue()


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _validate_import_file(file: UploadFile) -> str:
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    allowed_content_types = SUPPORTED_IMPORT_MIME_TYPES.get(extension)
    if allowed_content_types is None or content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Import file must be a JSON or CSV file",
        )
    return extension.removeprefix(".")


async def _read_import_file(file: UploadFile) -> bytes:
    try:
        content = await file.read(MAX_IMPORT_SIZE_BYTES + 1)
    finally:
        await file.close()

    if len(content) > MAX_IMPORT_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Import file exceeds the size limit",
        )
    if not content:
        raise _invalid_import("Import file is empty")
    return content


def _parse_import_records(content: bytes, import_format: str) -> list[dict[str, Any]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise _invalid_import("Import file must be valid UTF-8") from error

    if import_format == "json":
        records = _parse_json_records(text)
    else:
        records = _parse_csv_records(text)

    if not records:
        raise _invalid_import("Import contains no tasks")
    if len(records) > MAX_IMPORT_RECORDS:
        raise _invalid_import("Import contains too many tasks")
    return records


def _parse_json_records(text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise _invalid_import("Malformed JSON import") from error

    if not isinstance(payload, dict):
        raise _invalid_import("JSON import must be an object")

    if "tasks" in payload:
        tasks = payload["tasks"]
        if not isinstance(tasks, list) or not all(
            isinstance(task, dict) for task in tasks
        ):
            raise _invalid_import("JSON tasks must be a list of objects")
        return [dict(task) for task in tasks]

    projects = payload.get("projects")
    if not isinstance(projects, list):
        raise _invalid_import("JSON import must contain projects or tasks")

    records: list[dict[str, Any]] = []
    for project in projects:
        if not isinstance(project, dict) or not project.get("id"):
            raise _invalid_import("Each imported project must contain an id")
        tasks = project.get("tasks")
        if not isinstance(tasks, list):
            raise _invalid_import("Each imported project must contain a tasks list")
        for task in tasks:
            if not isinstance(task, dict):
                raise _invalid_import("JSON tasks must be objects")
            record = dict(task)
            task_project_id = record.get("project_id")
            if task_project_id and str(task_project_id) != str(project["id"]):
                raise _invalid_import("Task project_id does not match its project")
            record["project_id"] = project["id"]
            records.append(record)
    return records


def _parse_csv_records(text: str) -> list[dict[str, Any]]:
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if reader.fieldnames is None or not {"project_id", "title"}.issubset(
            reader.fieldnames
        ):
            raise _invalid_import("CSV import requires project_id and title columns")
        records = list(reader)
    except csv.Error as error:
        raise _invalid_import("Malformed CSV import") from error

    if any(None in record for record in records):
        raise _invalid_import("Malformed CSV row")
    return records


def _build_imported_task(
    db: Session,
    record: dict[str, Any],
    user_id: UUID,
    project_cache: dict[UUID, Project],
) -> Task:
    project_id = _parse_uuid(record.get("project_id"), "project_id")
    if project_id not in project_cache:
        project_cache[project_id] = _get_writable_project(db, project_id, user_id)

    title = record.get("title")
    if not isinstance(title, str) or not title.strip():
        raise _invalid_import("Each task requires a non-empty title")

    description = record.get("description")
    if description == "":
        description = None
    if description is not None and not isinstance(description, str):
        raise _invalid_import("Task description must be a string or null")

    raw_status = record.get("status") or TaskStatus.TODO.value
    try:
        task_status = TaskStatus(raw_status)
    except (TypeError, ValueError) as error:
        raise _invalid_import("Invalid task status") from error

    assignee_id = _parse_optional_uuid(record.get("assignee_id"), "assignee_id")
    if assignee_id is not None and db.scalar(
        select(User.id).where(User.id == assignee_id)
    ) is None:
        raise _invalid_import("Unknown task assignee")

    due_date = _parse_optional_date(record.get("due_date"))
    return Task(
        project_id=project_id,
        title=title.strip(),
        description=description,
        status=task_status,
        assignee_id=assignee_id,
        due_date=due_date,
    )


def _get_writable_project(db: Session, project_id: UUID, user_id: UUID) -> Project:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            _project_access_filter(user_id),
        )
    )
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    if project.owner_id == user_id:
        return project

    role = db.scalar(
        select(ProjectMember.role).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user_id,
        )
    )
    if role not in {ProjectRole.OWNER, ProjectRole.EDITOR}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project membership is read-only",
        )
    return project


def _parse_uuid(value: Any, field_name: str) -> UUID:
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _invalid_import(f"Invalid {field_name}") from error


def _parse_optional_uuid(value: Any, field_name: str) -> UUID | None:
    if value in (None, ""):
        return None
    return _parse_uuid(value, field_name)


def _parse_optional_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise _invalid_import("Invalid due_date")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise _invalid_import("Invalid due_date") from error


def _invalid_import(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
