import uuid
from pathlib import Path, PurePosixPath
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models.attachment import Attachment
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task
from app.models.user import User


router = APIRouter(tags=["Attachments"])

ALLOWED_ATTACHMENT_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "text/csv",
        "text/plain",
    }
)
SAFE_EXTENSIONS_BY_MIME_TYPE = {
    "application/pdf": frozenset({".pdf"}),
    "image/jpeg": frozenset({".jpg", ".jpeg"}),
    "image/png": frozenset({".png"}),
    "text/csv": frozenset({".csv"}),
    "text/plain": frozenset({".txt"}),
}
DEFAULT_EXTENSION_BY_MIME_TYPE = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "text/csv": ".csv",
    "text/plain": ".txt",
}
UPLOAD_URL_PREFIX = "/uploads"
UPLOAD_CHUNK_SIZE = 1024 * 1024


def get_attachments_current_user() -> User:
    """Fail closed until the shared JWT current-user dependency is available."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Shared current-user authentication is not available",
    )


DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_attachments_current_user)]
ApplicationSettings = Annotated[Settings, Depends(get_settings)]


@router.post(
    "/api/tasks/{task_id}/attachments",
    summary="Upload a task attachment",
    description=(
        "Upload a supported document or image to a task. Project owners and "
        "members with the owner or editor role may upload files."
    ),
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Read-only project access."},
        status.HTTP_404_NOT_FOUND: {
            "description": "Task not found or not visible."
        },
        413: {"description": "Uploaded file exceeds the configured size limit."},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {
            "description": "Uploaded file type is not supported."
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Shared current-user authentication is not integrated."
        },
    },
)
async def upload_attachment(
    task_id: UUID,
    file: Annotated[UploadFile, File(description="Document or image to attach.")],
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    settings: ApplicationSettings,
) -> dict[str, Any]:
    task = _get_accessible_task(db, task_id, current_user.id)
    project = _get_accessible_project(db, task.project_id, current_user.id)
    _require_project_editor(db, project, current_user.id)
    _validate_content_type(file.content_type)

    original_filename = file.filename or "unnamed"
    stored_filename = _generate_stored_filename(
        original_filename,
        file.content_type,
    )
    upload_directory = _upload_directory(settings)
    upload_directory.mkdir(parents=True, exist_ok=True)
    stored_path = upload_directory / stored_filename

    await _write_uploaded_file(
        file,
        stored_path,
        settings.max_upload_size_mb * 1024 * 1024,
    )

    attachment = Attachment(
        task_id=task.id,
        file_url=f"{UPLOAD_URL_PREFIX}/{stored_filename}",
        file_name=original_filename,
        uploaded_by=current_user.id,
    )
    try:
        db.add(attachment)
        db.commit()
    except Exception:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise

    db.refresh(attachment)
    return _success_response(attachment=_serialize_attachment(attachment))


@router.delete(
    "/api/attachments/{attachment_id}",
    summary="Delete a task attachment",
    description=(
        "Delete an attachment and its stored file. Project owners and members "
        "with the owner or editor role may delete attachments."
    ),
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Read-only project access."},
        status.HTTP_404_NOT_FOUND: {
            "description": "Attachment not found or not visible."
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Shared current-user authentication is not integrated."
        },
    },
)
def delete_attachment(
    attachment_id: UUID,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    settings: ApplicationSettings,
) -> dict[str, Any]:
    attachment = _get_accessible_attachment(db, attachment_id, current_user.id)
    task = _get_accessible_task(db, attachment.task_id, current_user.id)
    project = _get_accessible_project(db, task.project_id, current_user.id)
    _require_project_editor(db, project, current_user.id)

    stored_path = _safe_stored_path(attachment.file_url, _upload_directory(settings))
    if stored_path is not None:
        stored_path.unlink(missing_ok=True)

    try:
        db.delete(attachment)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return _success_response(success=True)


def _project_access_filter(user_id: UUID):
    member_project_ids = select(ProjectMember.project_id).where(
        ProjectMember.user_id == user_id
    )
    return or_(
        Project.owner_id == user_id,
        Project.id.in_(member_project_ids),
    )


def _get_accessible_task(db: Session, task_id: UUID, user_id: UUID) -> Task:
    task = db.scalar(
        select(Task)
        .join(Project, Task.project_id == Project.id)
        .where(
            Task.id == task_id,
            _project_access_filter(user_id),
        )
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task


def _get_accessible_attachment(
    db: Session,
    attachment_id: UUID,
    user_id: UUID,
) -> Attachment:
    attachment = db.scalar(
        select(Attachment)
        .join(Task, Attachment.task_id == Task.id)
        .join(Project, Task.project_id == Project.id)
        .where(
            Attachment.id == attachment_id,
            _project_access_filter(user_id),
        )
    )
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    return attachment


def _get_accessible_project(db: Session, project_id: UUID, user_id: UUID) -> Project:
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
    return project


def _require_project_editor(db: Session, project: Project, user_id: UUID) -> None:
    if project.owner_id == user_id:
        return

    member_role = db.scalar(
        select(ProjectMember.role).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user_id,
        )
    )
    if member_role not in {ProjectRole.OWNER, ProjectRole.EDITOR}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project membership is read-only",
        )


def _validate_content_type(content_type: str | None) -> None:
    if content_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported attachment type",
        )


def _generate_stored_filename(original_filename: str, content_type: str) -> str:
    original_suffix = Path(original_filename).suffix.lower()
    safe_extensions = SAFE_EXTENSIONS_BY_MIME_TYPE[content_type]
    extension = (
        original_suffix
        if original_suffix in safe_extensions
        else DEFAULT_EXTENSION_BY_MIME_TYPE[content_type]
    )
    return f"{uuid.uuid4().hex}{extension}"


async def _write_uploaded_file(
    file: UploadFile,
    stored_path: Path,
    max_size_bytes: int,
) -> None:
    bytes_written = 0
    try:
        with stored_path.open("xb") as destination:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                bytes_written += len(chunk)
                if bytes_written > max_size_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail="Attachment exceeds the configured size limit",
                    )
                destination.write(chunk)
    except BaseException:
        stored_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


def _upload_directory(settings: Settings) -> Path:
    return Path(settings.upload_dir).expanduser().resolve()


def _safe_stored_path(file_url: str, upload_directory: Path) -> Path | None:
    url_path = PurePosixPath(file_url)
    if url_path.parent != PurePosixPath(UPLOAD_URL_PREFIX):
        return None

    candidate = (upload_directory / url_path.name).resolve()
    if candidate.parent != upload_directory:
        return None
    return candidate


def _serialize_attachment(attachment: Attachment) -> dict[str, Any]:
    return {
        "id": attachment.id,
        "task_id": attachment.task_id,
        "file_url": attachment.file_url,
        "file_name": attachment.file_name,
        "uploaded_by": attachment.uploaded_by,
        "created_at": attachment.created_at,
    }


def _success_response(**data: Any) -> dict[str, Any]:
    return {"success": True, "data": data}
