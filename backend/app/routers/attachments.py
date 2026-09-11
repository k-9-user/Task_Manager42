import logging
import uuid
from pathlib import Path, PurePosixPath
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.project_permissions import lock_project_for_write
from app.models.attachment import Attachment
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task
from app.models.user import User


router = APIRouter(tags=["Attachments"])
logger = logging.getLogger(__name__)

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

ALLOWED_BANNER_MIME_TYPES = frozenset({"image/jpeg", "image/png"})


DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]
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
    },
)
async def upload_attachment(
    task_id: UUID,
    file: Annotated[UploadFile, File(description="Document or image to attach.")],
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    settings: ApplicationSettings,
) -> dict[str, Any]:
    project_id = db.scalar(select(Task.project_id).where(Task.id == task_id))
    if project_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    _validate_content_type(file.content_type)
    membership_role = db.scalar(
        select(ProjectMember.role).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        )
    )
    if membership_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if membership_role not in (ProjectRole.OWNER, ProjectRole.EDITOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project membership is read-only",
        )

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

    try:
        lock_project_for_write(
            db,
            project_id,
            current_user.id,
            ProjectRole.OWNER,
            ProjectRole.EDITOR,
            not_found_detail="Task not found",
        )
        task = db.scalar(
            select(Task)
            .where(Task.id == task_id)
            .execution_options(populate_existing=True)
        )
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found",
            )

        attachment = Attachment(
            task_id=task.id,
            file_url=f"{UPLOAD_URL_PREFIX}/{stored_filename}",
            file_name=original_filename,
            uploaded_by=current_user.id,
        )
        db.add(attachment)
        db.commit()
    except BaseException:
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
    },
)
def delete_attachment(
    attachment_id: UUID,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    settings: ApplicationSettings,
) -> dict[str, Any]:
    project_id = db.scalar(
        select(Task.project_id)
        .join(Attachment, Attachment.task_id == Task.id)
        .where(Attachment.id == attachment_id)
    )
    if project_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found",
        )
    lock_project_for_write(
        db, project_id, current_user.id, ProjectRole.OWNER, ProjectRole.EDITOR,
        not_found_detail="Attachment not found",
    )
    attachment = db.scalar(
        select(Attachment)
        .where(Attachment.id == attachment_id)
        .execution_options(populate_existing=True)
    )
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found",
        )

    stored_path = _safe_stored_path(attachment.file_url, _upload_directory(settings))
    try:
        db.delete(attachment)
        db.commit()
    except Exception:
        db.rollback()
        raise

    if stored_path is not None:
        try:
            stored_path.unlink(missing_ok=True)
        except OSError:
            logger.error(
                "attachment_cleanup_failed attachment_id=%s file=%s",
                attachment_id,
                stored_path.name,
            )

    return _success_response()


@router.post(
    "/api/tasks/{task_id}/banner",
    summary="Upload a task banner image",
    description=(
        "Upload a JPEG or PNG banner image for a task, replacing any existing "
        "banner. Project owners and members with the owner or editor role may "
        "upload a banner."
    ),
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Read-only project access."},
        status.HTTP_404_NOT_FOUND: {"description": "Task not found or not visible."},
        413: {"description": "Uploaded file exceeds the configured size limit."},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {
            "description": "Uploaded file type is not supported."
        },
    },
)
async def upload_task_banner(
    task_id: UUID,
    file: Annotated[UploadFile, File(description="JPEG or PNG banner image.")],
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    settings: ApplicationSettings,
) -> dict[str, Any]:
    project_id = db.scalar(select(Task.project_id).where(Task.id == task_id))
    if project_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    _validate_banner_content_type(file.content_type)
    membership_role = db.scalar(
        select(ProjectMember.role).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        )
    )
    if membership_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if membership_role not in (ProjectRole.OWNER, ProjectRole.EDITOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project membership is read-only",
        )

    stored_filename = _generate_stored_filename(file.filename or "banner", file.content_type)
    upload_directory = _upload_directory(settings)
    upload_directory.mkdir(parents=True, exist_ok=True)
    stored_path = upload_directory / stored_filename

    await _write_uploaded_file(
        file,
        stored_path,
        settings.max_upload_size_mb * 1024 * 1024,
    )

    try:
        lock_project_for_write(
            db,
            project_id,
            current_user.id,
            ProjectRole.OWNER,
            ProjectRole.EDITOR,
            not_found_detail="Task not found",
        )
        task = db.scalar(
            select(Task)
            .where(Task.id == task_id)
            .execution_options(populate_existing=True)
        )
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

        previous_banner_path = (
            _safe_stored_path(task.banner_url, upload_directory)
            if task.banner_url
            else None
        )
        task.banner_url = f"{UPLOAD_URL_PREFIX}/{stored_filename}"
        db.commit()
    except BaseException:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise

    if previous_banner_path is not None:
        previous_banner_path.unlink(missing_ok=True)

    db.refresh(task)
    return _success_response(task_id=task.id, banner_url=task.banner_url)


@router.delete(
    "/api/tasks/{task_id}/banner",
    summary="Remove a task banner image",
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Read-only project access."},
        status.HTTP_404_NOT_FOUND: {"description": "Task not found or not visible."},
    },
)
def delete_task_banner(
    task_id: UUID,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    settings: ApplicationSettings,
) -> dict[str, Any]:
    project_id = db.scalar(select(Task.project_id).where(Task.id == task_id))
    if project_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    lock_project_for_write(
        db, project_id, current_user.id, ProjectRole.OWNER, ProjectRole.EDITOR,
        not_found_detail="Task not found",
    )
    task = db.scalar(
        select(Task).where(Task.id == task_id).execution_options(populate_existing=True)
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    stored_path = (
        _safe_stored_path(task.banner_url, _upload_directory(settings))
        if task.banner_url
        else None
    )
    task.banner_url = None
    db.commit()

    if stored_path is not None:
        stored_path.unlink(missing_ok=True)

    return _success_response()


def _validate_content_type(content_type: str | None) -> None:
    if content_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported attachment type",
        )


def _validate_banner_content_type(content_type: str | None) -> None:
    if content_type not in ALLOWED_BANNER_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported banner image type",
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
