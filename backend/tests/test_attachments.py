from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base, get_db
from app.models.attachment import Attachment
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task
from app.models.user import User
from app.routers import attachments


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def current_user(db: Session) -> User:
    return _create_user(db, "attachment-user")


@pytest.fixture
def test_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        upload_dir=str(tmp_path / "uploads"),
        max_upload_size_mb=1,
    )


@pytest.fixture
def app(
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(attachments.router)

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_settings] = lambda: test_settings
    test_app.dependency_overrides[
        attachments.get_attachments_current_user
    ] = lambda: current_user
    return test_app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


def test_router_exposes_exact_attachment_routes():
    routes = {
        (method, route.path)
        for route in attachments.router.routes
        for method in route.methods
    }

    assert routes == {
        ("POST", "/api/tasks/{task_id}/attachments"),
        ("DELETE", "/api/attachments/{attachment_id}"),
    }


def test_openapi_documents_multipart_upload_without_api_key(app: FastAPI):
    schema = app.openapi()
    upload_operation = schema["paths"]["/api/tasks/{task_id}/attachments"]["post"]
    delete_operation = schema["paths"]["/api/attachments/{attachment_id}"]["delete"]

    assert upload_operation["summary"] == "Upload a task attachment"
    assert delete_operation["summary"] == "Delete a task attachment"
    assert upload_operation["requestBody"]["required"] is True
    assert "multipart/form-data" in upload_operation["requestBody"]["content"]
    assert all(
        parameter["name"] != "X-API-Key"
        for operation in (upload_operation, delete_operation)
        for parameter in operation.get("parameters", [])
    )


def test_missing_shared_current_user_dependency_fails_closed(
    db: Session,
    test_settings: SimpleNamespace,
):
    test_app = FastAPI()
    test_app.include_router(attachments.router)

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_settings] = lambda: test_settings

    with TestClient(test_app) as test_client:
        response = test_client.delete(f"/api/attachments/{uuid4()}")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_owner_can_upload_supported_pdf(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
):
    project = _create_project(db, current_user, "Owner upload project")
    task = _create_task(db, project, "Owner upload task")

    response = _upload(
        client,
        task,
        filename="project-spec.pdf",
        content=b"%PDF-test-content",
        content_type="application/pdf",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True
    attachment_data = response.json()["data"]["attachment"]
    assert set(attachment_data) == {
        "id",
        "task_id",
        "file_url",
        "file_name",
        "uploaded_by",
        "created_at",
    }
    assert _stored_path(test_settings, attachment_data["file_url"]).read_bytes() == (
        b"%PDF-test-content"
    )


@pytest.mark.parametrize("role", [ProjectRole.OWNER, ProjectRole.EDITOR])
def test_writable_project_member_can_upload(
    client: TestClient,
    db: Session,
    current_user: User,
    role: ProjectRole,
):
    project_owner = _create_user(db, f"{role.value}-upload-owner")
    project = _create_project(db, project_owner, f"{role.value} upload project")
    _add_member(db, project, current_user, role)
    task = _create_task(db, project, f"{role.value} upload task")

    response = _upload(client, task)

    assert response.status_code == status.HTTP_200_OK


def test_attachment_row_contains_correct_metadata(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Metadata project")
    task = _create_task(db, project, "Metadata task")

    response = _upload(client, task, filename="design-notes.pdf")
    attachment = db.scalar(select(Attachment))

    assert response.status_code == status.HTTP_200_OK
    assert attachment is not None
    assert attachment.task_id == task.id
    assert attachment.file_name == "design-notes.pdf"
    assert attachment.uploaded_by == current_user.id
    assert attachment.file_url == response.json()["data"]["attachment"]["file_url"]
    assert attachment.created_at is not None


def test_generated_physical_filename_differs_from_original(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
):
    project = _create_project(db, current_user, "Generated name project")
    task = _create_task(db, project, "Generated name task")

    response = _upload(client, task, filename="human-readable.pdf")
    stored_path = _stored_path(
        test_settings,
        response.json()["data"]["attachment"]["file_url"],
    )

    assert stored_path.name != "human-readable.pdf"
    assert stored_path.suffix == ".pdf"
    assert UUID(stored_path.stem)


def test_viewer_cannot_upload(
    client: TestClient,
    db: Session,
    current_user: User,
):
    owner = _create_user(db, "viewer-upload-owner")
    project = _create_project(db, owner, "Viewer upload project")
    _add_member(db, project, current_user, ProjectRole.VIEWER)
    task = _create_task(db, project, "Viewer upload task")

    response = _upload(client, task)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert db.scalars(select(Attachment)).all() == []


def test_unrelated_user_cannot_discover_task_for_upload(
    client: TestClient,
    db: Session,
    current_user: User,
):
    owner = _create_user(db, "private-upload-owner")
    project = _create_project(db, owner, "Private upload project")
    task = _create_task(db, project, "Private upload task")

    response = _upload(client, task)

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_missing_task_returns_404(client: TestClient):
    response = client.post(
        f"/api/tasks/{uuid4()}/attachments",
        files={"file": ("missing.pdf", b"content", "application/pdf")},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize(
    ("filename", "content_type", "expected_suffix"),
    [
        ("diagram.png", "image/png", ".png"),
        ("photo.jpeg", "image/jpeg", ".jpeg"),
    ],
)
def test_supported_image_is_accepted(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
    filename: str,
    content_type: str,
    expected_suffix: str,
):
    project = _create_project(db, current_user, f"{content_type} project")
    task = _create_task(db, project, f"{content_type} task")

    response = _upload(
        client,
        task,
        filename=filename,
        content=b"image-content",
        content_type=content_type,
    )

    assert response.status_code == status.HTTP_200_OK
    stored_path = _stored_path(
        test_settings,
        response.json()["data"]["attachment"]["file_url"],
    )
    assert stored_path.suffix == expected_suffix


def test_unsupported_type_is_rejected_without_writing_file(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
):
    project = _create_project(db, current_user, "Unsupported type project")
    task = _create_task(db, project, "Unsupported type task")

    response = _upload(
        client,
        task,
        filename="script.sh",
        content=b"#!/bin/sh",
        content_type="application/x-sh",
    )

    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert not Path(test_settings.upload_dir).exists()
    assert db.scalars(select(Attachment)).all() == []


def test_oversized_file_is_rejected_without_partial_file(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
):
    project = _create_project(db, current_user, "Oversized project")
    task = _create_task(db, project, "Oversized task")
    oversized_content = b"x" * (1024 * 1024 + 1)

    response = _upload(
        client,
        task,
        content=oversized_content,
    )

    assert response.status_code == 413
    assert list(Path(test_settings.upload_dir).iterdir()) == []
    assert db.scalars(select(Attachment)).all() == []


def test_empty_supported_file_is_accepted(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
):
    project = _create_project(db, current_user, "Empty file project")
    task = _create_task(db, project, "Empty file task")

    response = _upload(client, task, filename="empty.txt", content=b"", content_type="text/plain")

    assert response.status_code == status.HTTP_200_OK
    stored_path = _stored_path(
        test_settings,
        response.json()["data"]["attachment"]["file_url"],
    )
    assert stored_path.stat().st_size == 0


def test_small_valid_file_content_is_preserved(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
):
    project = _create_project(db, current_user, "Small file project")
    task = _create_task(db, project, "Small file task")

    response = _upload(
        client,
        task,
        filename="notes.txt",
        content=b"small task note",
        content_type="text/plain",
    )

    stored_path = _stored_path(
        test_settings,
        response.json()["data"]["attachment"]["file_url"],
    )
    assert response.status_code == status.HTTP_200_OK
    assert stored_path.read_bytes() == b"small task note"


def test_traversal_style_client_filename_cannot_escape_upload_directory(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
    tmp_path: Path,
):
    project = _create_project(db, current_user, "Traversal project")
    task = _create_task(db, project, "Traversal task")

    response = _upload(client, task, filename="../../outside.pdf")
    attachment_data = response.json()["data"]["attachment"]
    stored_path = _stored_path(test_settings, attachment_data["file_url"])

    assert response.status_code == status.HTTP_200_OK
    assert attachment_data["file_name"] == "../../outside.pdf"
    assert stored_path.resolve().parent == Path(test_settings.upload_dir).resolve()
    assert not (tmp_path / "outside.pdf").exists()


def test_file_is_written_inside_configured_upload_directory(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
):
    project = _create_project(db, current_user, "Storage project")
    task = _create_task(db, project, "Storage task")

    response = _upload(client, task)
    stored_path = _stored_path(
        test_settings,
        response.json()["data"]["attachment"]["file_url"],
    )

    assert stored_path.is_file()
    assert stored_path.resolve().parent == Path(test_settings.upload_dir).resolve()


def test_original_filename_is_retained_as_metadata(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Original filename project")
    task = _create_task(db, project, "Original filename task")

    response = _upload(client, task, filename="meeting-notes.csv", content_type="text/csv")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["attachment"]["file_name"] == "meeting-notes.csv"


def test_internal_stored_filenames_are_unique_and_safe(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
):
    project = _create_project(db, current_user, "Unique filename project")
    task = _create_task(db, project, "Unique filename task")

    first_response = _upload(client, task, filename="duplicate.pdf")
    second_response = _upload(client, task, filename="duplicate.pdf")
    first_path = _stored_path(
        test_settings,
        first_response.json()["data"]["attachment"]["file_url"],
    )
    second_path = _stored_path(
        test_settings,
        second_response.json()["data"]["attachment"]["file_url"],
    )

    assert first_path != second_path
    assert UUID(first_path.stem)
    assert UUID(second_path.stem)
    assert first_path.parent == second_path.parent == Path(test_settings.upload_dir)


def test_owner_can_delete_attachment_and_file(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
):
    project = _create_project(db, current_user, "Owner delete project")
    task = _create_task(db, project, "Owner delete task")
    attachment, stored_path = _create_attachment(
        db,
        task,
        current_user,
        test_settings,
    )
    attachment_id = attachment.id

    response = client.delete(f"/api/attachments/{attachment_id}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"success": True, "data": {"success": True}}
    assert db.get(Attachment, attachment_id) is None
    assert not stored_path.exists()


@pytest.mark.parametrize("role", [ProjectRole.OWNER, ProjectRole.EDITOR])
def test_writable_project_member_can_delete_attachment(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
    role: ProjectRole,
):
    owner = _create_user(db, f"{role.value}-delete-owner")
    project = _create_project(db, owner, f"{role.value} delete project")
    _add_member(db, project, current_user, role)
    task = _create_task(db, project, f"{role.value} delete task")
    attachment, _ = _create_attachment(
        db,
        task,
        current_user,
        test_settings,
    )

    response = client.delete(f"/api/attachments/{attachment.id}")

    assert response.status_code == status.HTTP_200_OK


def test_viewer_cannot_delete_attachment(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
):
    owner = _create_user(db, "viewer-delete-owner")
    project = _create_project(db, owner, "Viewer delete project")
    _add_member(db, project, current_user, ProjectRole.VIEWER)
    task = _create_task(db, project, "Viewer delete task")
    attachment, stored_path = _create_attachment(
        db,
        task,
        current_user,
        test_settings,
    )

    response = client.delete(f"/api/attachments/{attachment.id}")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert db.get(Attachment, attachment.id) is not None
    assert stored_path.exists()


def test_unrelated_attachment_is_hidden(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
):
    owner = _create_user(db, "private-attachment-owner")
    project = _create_project(db, owner, "Private attachment project")
    task = _create_task(db, project, "Private attachment task")
    attachment, stored_path = _create_attachment(
        db,
        task,
        owner,
        test_settings,
    )

    response = client.delete(f"/api/attachments/{attachment.id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert db.get(Attachment, attachment.id) is not None
    assert stored_path.exists()


def test_missing_physical_file_does_not_block_database_cleanup(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
):
    project = _create_project(db, current_user, "Missing file project")
    task = _create_task(db, project, "Missing file task")
    attachment, stored_path = _create_attachment(
        db,
        task,
        current_user,
        test_settings,
        create_physical_file=False,
    )
    attachment_id = attachment.id

    response = client.delete(f"/api/attachments/{attachment_id}")

    assert not stored_path.exists()
    assert response.status_code == status.HTTP_200_OK
    assert db.get(Attachment, attachment_id) is None


def test_unsafe_database_file_url_cannot_delete_outside_upload_directory(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
    tmp_path: Path,
):
    project = _create_project(db, current_user, "Unsafe URL project")
    task = _create_task(db, project, "Unsafe URL task")
    outside_file = tmp_path / "outside.txt"
    outside_file.write_bytes(b"must remain")
    attachment = Attachment(
        task_id=task.id,
        file_url="/uploads/../outside.txt",
        file_name="outside.txt",
        uploaded_by=current_user.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    attachment_id = attachment.id

    response = client.delete(f"/api/attachments/{attachment_id}")

    assert response.status_code == status.HTTP_200_OK
    assert outside_file.read_bytes() == b"must remain"
    assert db.get(Attachment, attachment_id) is None


def test_database_failure_after_write_removes_new_file(
    client: TestClient,
    db: Session,
    current_user: User,
    test_settings: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
):
    project = _create_project(db, current_user, "Database failure project")
    task = _create_task(db, project, "Database failure task")
    rollback_spy = MagicMock(wraps=db.rollback)
    monkeypatch.setattr(db, "rollback", rollback_spy)
    monkeypatch.setattr(db, "commit", MagicMock(side_effect=RuntimeError("DB failed")))

    with pytest.raises(RuntimeError, match="DB failed"):
        _upload(client, task, filename="cleanup.pdf", content=b"written first")

    assert rollback_spy.call_count == 1
    assert list(Path(test_settings.upload_dir).iterdir()) == []


def _upload(
    client: TestClient,
    task: Task,
    *,
    filename: str = "attachment.pdf",
    content: bytes = b"attachment content",
    content_type: str = "application/pdf",
):
    return client.post(
        f"/api/tasks/{task.id}/attachments",
        files={"file": (filename, content, content_type)},
    )


def _stored_path(settings: SimpleNamespace, file_url: str) -> Path:
    return Path(settings.upload_dir) / Path(file_url).name


def _create_user(db: Session, label: str) -> User:
    unique_label = f"{label}-{uuid4().hex}"
    user = User(
        email=f"{unique_label}@example.com",
        username=unique_label,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_project(db: Session, owner: User, name: str) -> Project:
    project = Project(name=name, owner_id=owner.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _add_member(
    db: Session,
    project: Project,
    user: User,
    role: ProjectRole,
) -> ProjectMember:
    member = ProjectMember(project_id=project.id, user_id=user.id, role=role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def _create_task(db: Session, project: Project, title: str) -> Task:
    task = Task(project_id=project.id, title=title)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _create_attachment(
    db: Session,
    task: Task,
    uploader: User,
    settings: SimpleNamespace,
    *,
    create_physical_file: bool = True,
) -> tuple[Attachment, Path]:
    stored_filename = f"{uuid4().hex}.pdf"
    stored_path = Path(settings.upload_dir) / stored_filename
    if create_physical_file:
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        stored_path.write_bytes(b"stored attachment")

    attachment = Attachment(
        task_id=task.id,
        file_url=f"/uploads/{stored_filename}",
        file_name="original.pdf",
        uploaded_by=uploader.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment, stored_path
