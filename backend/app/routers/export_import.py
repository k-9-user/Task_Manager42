import csv
import io
import json
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
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.project_permissions import lock_project_for_write, visible_project_ids
from app.database import get_db
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task
from app.models.user import User
from app.schemas.common import SuccessEnvelope
from app.schemas.project import ProjectResponse
from app.schemas.task import TaskImportRecord, TaskSummary


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


DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "/api/export",
    summary="Export visible projects and tasks",
    description=(
        "Download visible project and task data as deterministic JSON or flat CSV. "
        "Only projects where the authenticated user is a member are exported; "
        "pass project_id to export a single one."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Unsupported export format."},
        status.HTTP_404_NOT_FOUND: {"description": "Project not found or not visible."},
    },
)
def export_data(
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    export_format: Annotated[
        str,
        Query(alias="format", description="Download format: json or csv."),
    ],
    project_id: Annotated[
        UUID | None,
        Query(description="Export a single visible project instead of every one."),
    ] = None,
) -> Response:
    if export_format not in SUPPORTED_EXPORT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export format must be json or csv",
        )

    projects, tasks_by_project = _load_visible_export_data(
        db, current_user.id, project_id
    )
    if export_format == "json":
        content = json.dumps(
            {
                "projects": [
                    {
                        **_json(ProjectResponse, project),
                        "tasks": [_json(TaskSummary, task) for task in tasks_by_project[project.id]],
                    }
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
        "Import JSON or CSV task data. A project referenced by the file is reused "
        "when it exists and the caller may write to it, and created otherwise, so an "
        "export can be imported into another account. The entire file is validated "
        "before everything is committed in one transaction."
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
    },
)
async def import_data(
    file: Annotated[
        UploadFile,
        File(description="JSON or CSV task export to import."),
    ],
    db: DatabaseSession,
    current_user: AuthenticatedUser,
) -> SuccessEnvelope:
    import_format = _validate_import_file(file)
    raw_content = await _read_import_file(file)
    records = _parse_import_records(raw_content, import_format)

    validated_records = _validate_task_import_records(records)
    targets, created = _resolve_import_projects(db, validated_records, current_user)
    validated_tasks = [
        _build_imported_task(
            db, record, targets[record.project_id], created, current_user.id
        )
        for record in validated_records
    ]
    db.add_all(validated_tasks)
    db.commit()

    return SuccessEnvelope(
        data={"imported_count": len(validated_tasks), "created_projects": len(created)}
    )


def _load_visible_export_data(
    db: Session,
    user_id: UUID,
    project_id: UUID | None = None,
) -> tuple[list[Project], dict[UUID, list[Task]]]:
    filters = [Project.id.in_(visible_project_ids(user_id))]
    if project_id is not None:
        filters.append(Project.id == project_id)

    projects = list(
        db.scalars(
            select(Project)
            .where(*filters)
            .order_by(Project.created_at.asc(), Project.id.asc())
        ).all()
    )
    if project_id is not None and not projects:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
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


def _json(schema: type[BaseModel], row: Any) -> dict[str, Any]:
    return schema.model_validate(row).model_dump(mode="json")


def _serialize_csv(
    projects: list[Project],
    tasks_by_project: dict[UUID, list[Task]],
) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for project in projects:
        for task in tasks_by_project[project.id]:
            row = _json(TaskSummary, task)
            writer.writerow(
                {
                    key: _safe_csv_cell(value)
                    for key, value in {
                        "project_id": row["project_id"],
                        "project_name": project.name,
                        "task_id": row["id"],
                        "title": row["title"],
                        "description": row["description"] or "",
                        "status": row["status"],
                        "assignee_id": row["assignee_id"] or "",
                        "due_date": row["due_date"] or "",
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }.items()
                }
            )
    return output.getvalue()


def _safe_csv_cell(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    trimmed = value.lstrip()
    if value[0] in "\t\r\n" or (trimmed and trimmed[0] in "=+-@"):
        return f"'{value}"
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
            if project.get("name"):
                record.setdefault("project_name", project["name"])
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


def _validate_task_import_records(
    records: list[dict[str, Any]],
) -> list[TaskImportRecord]:
    try:
        return [
            TaskImportRecord.model_validate(record)
            for record in records
        ]
    except ValidationError as error:
        raise _invalid_import("Invalid task import data") from error


def _may_write(db: Session, project_id: UUID, user_id: UUID) -> bool:
    return db.scalar(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.role.in_((ProjectRole.OWNER, ProjectRole.EDITOR)),
        )
    ) is not None


def _resolve_import_projects(
    db: Session,
    records: list[TaskImportRecord],
    user: User,
) -> tuple[dict[UUID, UUID], set[UUID]]:
    """Map every referenced project to a writable one, creating it when there is none.

    A project the caller cannot write to — absent here, or owned by somebody else — is
    recreated from the exported name, so an export stays importable across accounts.
    """

    names: dict[UUID, str] = {}
    for record in records:
        if record.project_name and record.project_id not in names:
            names[record.project_id] = record.project_name

    targets: dict[UUID, UUID] = {}
    created: set[UUID] = set()
    for project_id in sorted({record.project_id for record in records}):
        if _may_write(db, project_id, user.id):
            lock_project_for_write(
                db, project_id, user.id, ProjectRole.OWNER, ProjectRole.EDITOR,
            )
            targets[project_id] = project_id
            continue

        name = names.get(project_id)
        if not name:
            raise _invalid_import("Imported project name is required to create it")
        project = Project(name=name, owner_id=user.id)
        db.add(project)
        db.flush()
        db.add(
            ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.OWNER)
        )
        targets[project_id] = project.id
        created.add(project.id)
    return targets, created


def _build_imported_task(
    db: Session,
    record: TaskImportRecord,
    project_id: UUID,
    created: set[UUID],
    importer_id: UUID,
) -> Task:
    """A project created by this import has one member, so only they can be assigned."""

    assignee_id = record.assignee_id
    if project_id in created:
        assignee_id = assignee_id if assignee_id == importer_id else None
    elif assignee_id is not None and db.scalar(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == assignee_id,
        )
    ) is None:
        raise _invalid_import("Task assignee must be a project member")

    return Task(
        project_id=project_id,
        title=record.title,
        description=record.description,
        status=record.status,
        assignee_id=assignee_id,
        due_date=record.due_date,
    )


def _invalid_import(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
