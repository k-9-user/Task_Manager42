"""Stored upload files: safe paths on disk and cleanup after task deletions."""

import csv
import io
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


def validate_upload_content(stored_path: Path, content_type: str) -> None:
    """Recognize allowed formats without claiming complete image/PDF integrity."""

    signatures = {
        "image/png": b"\x89PNG\r\n\x1a\n",
        "image/jpeg": b"\xff\xd8\xff",
        "application/pdf": b"%PDF-",
    }
    with stored_path.open("rb") as source:
        header = source.read(8)
    if not header:
        raise ValueError("Empty upload")
    if content_type in signatures:
        if not header.startswith(signatures[content_type]):
            raise ValueError("Invalid file signature")
        return

    text = stored_path.read_text(encoding="utf-8-sig")
    if not text or any(
        (ord(character) < 32 and character not in "\t\r\n") or ord(character) == 127
        for character in text
    ):
        raise ValueError("Invalid text file")
    if content_type == "text/csv":
        columns = None
        try:
            for row in csv.reader(io.StringIO(text, newline=""), strict=True):
                if not row:
                    continue
                if columns is None:
                    columns = len(row)
                elif len(row) != columns:
                    raise ValueError("Inconsistent CSV columns")
        except csv.Error as error:
            raise ValueError("Invalid CSV") from error
        if columns is None:
            raise ValueError("Empty CSV")


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
