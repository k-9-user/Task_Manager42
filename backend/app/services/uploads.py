"""Stored upload files: safe paths on disk and cleanup after task deletions."""

import logging
from pathlib import Path, PurePosixPath

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.attachment import Attachment
from app.models.task import Task


UPLOAD_URL_PREFIX = "/uploads"

logger = logging.getLogger(__name__)


def upload_root(settings: Settings) -> Path:
    return Path(settings.upload_dir).expanduser().resolve()


def safe_stored_path(file_url: str, upload_directory: Path) -> Path | None:
    url_path = PurePosixPath(file_url)
    if url_path.parent != PurePosixPath(UPLOAD_URL_PREFIX):
        return None

    candidate = (upload_directory / url_path.name).resolve()
    if candidate.parent != upload_directory:
        return None
    return candidate


def task_files(db: Session, settings: Settings, *criteria: ColumnElement[bool]) -> list[Path]:
    """Attachment and banner files of the tasks matching ``criteria``."""

    file_urls = [
        *db.scalars(
            select(Attachment.file_url).where(
                Attachment.task_id.in_(select(Task.id).where(*criteria))
            )
        ),
        *db.scalars(select(Task.banner_url).where(*criteria, Task.banner_url.is_not(None))),
    ]
    upload_directory = upload_root(settings)
    return [
        path
        for file_url in file_urls
        if (path := safe_stored_path(file_url, upload_directory)) is not None
    ]


def remove_files(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.error("upload_cleanup_failed file=%s", path.name)
