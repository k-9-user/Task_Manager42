import logging
import mimetypes
import uuid
from pathlib import Path, PurePosixPath
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.project_permissions import (
    get_membership_or_404,
    lock_project_for_write,
    lock_task_for_write,
)
from app.config import Settings, get_settings
from app.database import get_db
from app.models.attachment import Attachment
from app.models.project_member import ProjectRole
from app.models.task import Task
from app.models.user import User
from app.schemas.common import SimpleSuccessResponse, SuccessEnvelope
from app.services.gamification import Track, record_activity
from app.services.uploads import UPLOAD_URL_PREFIX, safe_stored_path, upload_root
from app.utils.validators import has_control_characters


router = APIRouter(tags=["Attachments"])
logger = logging.getLogger(__name__)

ATTACHMENT_EXTENSIONS = {
    "application/pdf": (".pdf",),
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
    "text/csv": (".csv",),
    "text/plain": (".txt",),
}
BANNER_TYPES = frozenset({"image/jpeg", "image/png"})
WRITE_ROLES = (ProjectRole.OWNER, ProjectRole.EDITOR)
UPLOAD_CHUNK_SIZE = 1024 * 1024

DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]
ApplicationSettings = Annotated[Settings, Depends(get_settings)]


@router.get("/api/tasks/{task_id}/attachments", summary="List task attachments")
def list_task_attachments(
    task_id: UUID,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
) -> SuccessEnvelope:
    project_id = _task_project_id(db, task_id)
    get_membership_or_404(db, project_id, current_user.id, "Task not found")

    task_attachments = db.scalars(
        select(Attachment)
        .where(Attachment.task_id == task_id)
        .order_by(Attachment.created_at.asc(), Attachment.id.asc())
    ).all()
    return SuccessEnvelope(
        data={"attachments": [_serialize_attachment_metadata(item) for item in task_attachments]}
    )


@router.post("/api/tasks/{task_id}/attachments", summary="Upload a task attachment")
async def upload_attachment(
    task_id: UUID,
    file: Annotated[UploadFile, File(description="Document or image to attach.")],
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    settings: ApplicationSettings,
) -> SuccessEnvelope:
    original_filename, stored_path = await _stage_upload(
        db, task_id, current_user.id, file, settings,
        ATTACHMENT_EXTENSIONS, "Unsupported attachment type", "unnamed",
    )
    try:
        task = lock_task_for_write(db, task_id, current_user.id, *WRITE_ROLES)
        attachment = Attachment(
            task_id=task.id,
            file_url=f"{UPLOAD_URL_PREFIX}/{stored_path.name}",
            file_name=original_filename,
            uploaded_by=current_user.id,
        )
        db.add(attachment)
        db.flush()
        record_activity(db, current_user.id, Track.FILES, attachment.id)
        db.commit()
    except BaseException:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise

    db.refresh(attachment)
    return SuccessEnvelope(data={"attachment": _serialize_attachment(attachment)})


@router.get(
    "/api/attachments/{attachment_id}",
    response_class=FileResponse,
    summary="Download a task attachment",
)
def download_attachment(
    attachment_id: UUID,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    settings: ApplicationSettings,
) -> FileResponse:
    attachment = db.scalar(select(Attachment).where(Attachment.id == attachment_id))
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    project_id = db.scalar(select(Task.project_id).where(Task.id == attachment.task_id))
    if project_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    get_membership_or_404(db, project_id, current_user.id, "Attachment not found")

    stored_path = safe_stored_path(attachment.file_url, upload_root(settings))
    if stored_path is None or not stored_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file not found"
        )

    return FileResponse(
        stored_path,
        filename=_safe_download_filename(attachment.file_name),
        media_type=_attachment_content_type(stored_path.name),
        content_disposition_type="inline",
    )


@router.delete("/api/attachments/{attachment_id}", summary="Delete a task attachment")
def delete_attachment(
    attachment_id: UUID,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    settings: ApplicationSettings,
) -> SimpleSuccessResponse:
    project_id = db.scalar(
        select(Task.project_id)
        .join(Attachment, Attachment.task_id == Task.id)
        .where(Attachment.id == attachment_id)
    )
    if project_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    lock_project_for_write(
        db, project_id, current_user.id, *WRITE_ROLES,
        not_found_detail="Attachment not found",
    )
    attachment = db.scalar(
        select(Attachment)
        .where(Attachment.id == attachment_id)
        .execution_options(populate_existing=True)
    )
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    stored_path = safe_stored_path(attachment.file_url, upload_root(settings))
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

    return SimpleSuccessResponse()


@router.post("/api/tasks/{task_id}/banner", summary="Upload a task banner image")
async def upload_task_banner(
    task_id: UUID,
    file: Annotated[UploadFile, File(description="JPEG or PNG banner image.")],
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    settings: ApplicationSettings,
) -> SuccessEnvelope:
    _original_filename, stored_path = await _stage_upload(
        db, task_id, current_user.id, file, settings,
        BANNER_TYPES, "Unsupported banner image type", "banner",
    )
    try:
        task = lock_task_for_write(db, task_id, current_user.id, *WRITE_ROLES)
        previous_banner_path = (
            safe_stored_path(task.banner_url, stored_path.parent) if task.banner_url else None
        )
        task.banner_url = f"{UPLOAD_URL_PREFIX}/{stored_path.name}"
        db.commit()
    except BaseException:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise

    if previous_banner_path is not None:
        previous_banner_path.unlink(missing_ok=True)

    db.refresh(task)
    return SuccessEnvelope(data={"task_id": task.id, "banner_url": task.banner_url})


@router.get("/api/tasks/{task_id}/banner/file", summary="Download a task banner image")
def download_task_banner(
    task_id: UUID,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    settings: ApplicationSettings,
) -> FileResponse:
    project_id = _task_project_id(db, task_id)
    get_membership_or_404(db, project_id, current_user.id)

    task = db.scalar(select(Task).where(Task.id == task_id))
    if task is None or not task.banner_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")

    stored_path = safe_stored_path(task.banner_url, upload_root(settings))
    if stored_path is None or not stored_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")

    return FileResponse(stored_path)


def _task_project_id(db: Session, task_id: UUID) -> UUID:
    project_id = db.scalar(select(Task.project_id).where(Task.id == task_id))
    if project_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return project_id


async def _stage_upload(
    db: Session,
    task_id: UUID,
    user_id: UUID,
    file: UploadFile,
    settings: Settings,
    allowed_types,
    type_error: str,
    fallback_name: str,
) -> tuple[str, Path]:
    """Check access and the file, then write it before the project lock is taken."""

    project_id = _task_project_id(db, task_id)
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=type_error)
    membership = get_membership_or_404(db, project_id, user_id, "Task not found")
    if membership.role not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project membership is read-only",
        )

    original_filename = file.filename or fallback_name
    _validate_original_filename(original_filename)
    upload_directory = upload_root(settings)
    upload_directory.mkdir(parents=True, exist_ok=True)
    stored_path = upload_directory / _generate_stored_filename(
        original_filename, file.content_type
    )
    await _write_uploaded_file(file, stored_path, settings.max_upload_size_mb * 1024 * 1024)
    return original_filename, stored_path


def _validate_original_filename(filename: str) -> None:
    if len(filename) > 255 or has_control_characters(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid attachment filename",
        )


def _generate_stored_filename(original_filename: str, content_type: str) -> str:
    extensions = ATTACHMENT_EXTENSIONS[content_type]
    suffix = Path(original_filename).suffix.lower()
    return f"{uuid.uuid4().hex}{suffix if suffix in extensions else extensions[0]}"


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


def _safe_download_filename(file_name: str) -> str:
    filename = PurePosixPath(file_name.replace("\\", "/")).name
    filename = "".join(character for character in filename if not has_control_characters(character))
    return filename if filename not in {"", ".", ".."} else "attachment"


def _attachment_content_type(stored_filename: str) -> str:
    return mimetypes.guess_type(stored_filename)[0] or "application/octet-stream"


def _serialize_attachment_metadata(attachment: Attachment) -> dict[str, Any]:
    return {
        "id": attachment.id,
        "filename": _safe_download_filename(attachment.file_name),
        "content_type": _attachment_content_type(PurePosixPath(attachment.file_url).name),
        "created_at": attachment.created_at,
    }


def _serialize_attachment(attachment: Attachment) -> dict[str, Any]:
    return {
        "id": attachment.id,
        "task_id": attachment.task_id,
        "file_url": attachment.file_url,
        "file_name": attachment.file_name,
        "uploaded_by": attachment.uploaded_by,
        "created_at": attachment.created_at,
    }
