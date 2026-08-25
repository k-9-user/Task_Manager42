import csv
import io
import json
from collections.abc import Generator
from datetime import date, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.database import Base, get_db
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.routers import export_import


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
    return _create_user(db, "export-import-user")


@pytest.fixture
def app(db: Session, current_user: User) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(export_import.router)

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_current_user] = lambda: current_user
    return test_app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


def test_router_exposes_exact_export_import_routes():
    routes = {
        (method, route.path)
        for route in export_import.router.routes
        for method in route.methods
    }

    assert routes == {
        ("GET", "/api/export"),
        ("POST", "/api/import"),
    }


def test_openapi_documents_formats_without_api_key(app: FastAPI):
    schema = app.openapi()
    export_operation = schema["paths"]["/api/export"]["get"]
    import_operation = schema["paths"]["/api/import"]["post"]

    assert export_operation["summary"] == "Export visible projects and tasks"
    assert import_operation["summary"] == "Import tasks into existing projects"
    assert export_operation["description"]
    assert import_operation["description"]
    assert "multipart/form-data" in import_operation["requestBody"]["content"]
    assert all(
        parameter["name"] != "X-API-Key"
        for operation in (export_operation, import_operation)
        for parameter in operation.get("parameters", [])
    )


def test_missing_shared_current_user_dependency_fails_closed(db: Session):
    test_app = FastAPI()
    test_app.include_router(export_import.router)

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app) as test_client:
        response = test_client.get("/api/export", params={"format": "json"})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_json_export_is_downloadable(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "JSON project")
    _create_task(db, project, "JSON task")

    response = client.get("/api/export", params={"format": "json"})

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/json"
    assert response.headers["content-disposition"] == (
        'attachment; filename="task-export.json"'
    )
    assert response.json()["projects"][0]["name"] == "JSON project"


def test_csv_export_is_downloadable(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "CSV project")
    _create_task(db, project, "CSV task")

    response = client.get("/api/export", params={"format": "csv"})
    rows = list(csv.DictReader(io.StringIO(response.text)))

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="task-export.csv"'
    )
    assert tuple(rows[0]) == export_import.CSV_COLUMNS
    assert rows[0]["project_name"] == "CSV project"
    assert rows[0]["title"] == "CSV task"


def test_owned_project_is_exported(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Owned export project")
    task = _create_task(db, project, "Owned export task")

    response = client.get("/api/export", params={"format": "json"})
    exported_project = response.json()["projects"][0]

    assert exported_project["id"] == str(project.id)
    assert exported_project["tasks"][0]["id"] == str(task.id)


def test_member_project_is_exported(
    client: TestClient,
    db: Session,
    current_user: User,
):
    owner = _create_user(db, "member-export-owner")
    project = _create_project(db, owner, "Member export project")
    _add_member(db, project, current_user, ProjectRole.VIEWER)
    task = _create_task(db, project, "Member export task")

    response = client.get("/api/export", params={"format": "json"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["projects"][0]["id"] == str(project.id)
    assert response.json()["projects"][0]["tasks"][0]["id"] == str(task.id)


def test_unrelated_project_is_excluded_from_export(
    client: TestClient,
    db: Session,
    current_user: User,
):
    visible_project = _create_project(db, current_user, "Visible export project")
    visible_task = _create_task(db, visible_project, "Visible export task")
    other_user = _create_user(db, "private-export-owner")
    private_project = _create_project(db, other_user, "Private export project")
    _create_task(db, private_project, "Private export task")

    response = client.get("/api/export", params={"format": "json"})
    payload_text = response.text

    assert response.status_code == status.HTTP_200_OK
    assert str(visible_task.id) in payload_text
    assert str(private_project.id) not in payload_text
    assert "Private export task" not in payload_text


def test_invalid_export_format_is_rejected(client: TestClient):
    response = client.get("/api/export", params={"format": "xml"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_json_export_serializes_enum_date_datetime_and_uuid(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Serialization project")
    created_at = datetime(2026, 3, 4, 5, 6, 7)
    task = _create_task(
        db,
        project,
        "Serialization task",
        task_status=TaskStatus.IN_PROGRESS,
        assignee_id=current_user.id,
        due_date=date(2026, 4, 5),
        created_at=created_at,
    )

    response = client.get("/api/export", params={"format": "json"})
    exported_task = response.json()["projects"][0]["tasks"][0]

    assert exported_task == {
        "id": str(task.id),
        "project_id": str(project.id),
        "title": "Serialization task",
        "description": None,
        "status": "in_progress",
        "assignee_id": str(current_user.id),
        "due_date": "2026-04-05",
        "created_at": created_at.isoformat(),
        "updated_at": created_at.isoformat(),
    }


def test_csv_export_uses_standard_csv_escaping(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Quoted, project")
    _create_task(
        db,
        project,
        "Quoted, task",
        description="First line\nSecond line",
    )

    response = client.get("/api/export", params={"format": "csv"})
    row = list(csv.DictReader(io.StringIO(response.text)))[0]

    assert row["project_name"] == "Quoted, project"
    assert row["title"] == "Quoted, task"
    assert row["description"] == "First line\nSecond line"


def test_owner_can_import_valid_json(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "JSON import project")
    payload = {
        "projects": [
            {
                "id": str(project.id),
                "name": project.name,
                "tasks": [
                    {
                        "project_id": str(project.id),
                        "title": "Imported JSON task",
                        "description": "Imported description",
                        "status": "done",
                        "due_date": "2026-05-06",
                    }
                ],
            }
        ]
    }

    response = _import_json(client, payload)
    imported_task = db.scalar(select(Task))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"success": True, "data": {"imported_count": 1}}
    assert imported_task is not None
    assert imported_task.project_id == project.id
    assert imported_task.title == "Imported JSON task"
    assert imported_task.status is TaskStatus.DONE
    assert imported_task.due_date == date(2026, 5, 6)


def test_valid_csv_import_works(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "CSV import project")
    content = _csv_import_content(
        [
            {
                "project_id": str(project.id),
                "title": "Imported CSV task",
                "description": "CSV description",
                "status": "in_progress",
                "assignee_id": "",
                "due_date": "2026-06-07",
            }
        ]
    )

    response = _import_csv(client, content)
    imported_task = db.scalar(select(Task))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["imported_count"] == 1
    assert imported_task is not None
    assert imported_task.title == "Imported CSV task"
    assert imported_task.status is TaskStatus.IN_PROGRESS


def test_imported_count_matches_all_inserted_tasks(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Count import project")
    payload = {
        "tasks": [
            {"project_id": str(project.id), "title": "First imported task"},
            {"project_id": str(project.id), "title": "Second imported task"},
        ]
    }

    response = _import_json(client, payload)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"success": True, "data": {"imported_count": 2}}
    assert len(db.scalars(select(Task)).all()) == 2


@pytest.mark.parametrize("role", [ProjectRole.OWNER, ProjectRole.EDITOR])
def test_writable_project_member_can_import(
    client: TestClient,
    db: Session,
    current_user: User,
    role: ProjectRole,
):
    owner = _create_user(db, f"{role.value}-import-owner")
    project = _create_project(db, owner, f"{role.value} import project")
    _add_member(db, project, current_user, role)
    payload = {
        "tasks": [
            {
                "project_id": str(project.id),
                "title": f"{role.value} imported task",
            }
        ]
    }

    response = _import_json(client, payload)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["imported_count"] == 1


def test_viewer_cannot_import_tasks(
    client: TestClient,
    db: Session,
    current_user: User,
):
    owner = _create_user(db, "viewer-import-owner")
    project = _create_project(db, owner, "Viewer import project")
    _add_member(db, project, current_user, ProjectRole.VIEWER)

    response = _import_json(
        client,
        {"tasks": [{"project_id": str(project.id), "title": "Forbidden task"}]},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert db.scalars(select(Task)).all() == []


def test_unrelated_project_is_hidden_during_import(
    client: TestClient,
    db: Session,
    current_user: User,
):
    owner = _create_user(db, "private-import-owner")
    project = _create_project(db, owner, "Private import project")

    response = _import_json(
        client,
        {"tasks": [{"project_id": str(project.id), "title": "Private task"}]},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert db.scalars(select(Task)).all() == []


def test_unknown_project_is_rejected(client: TestClient):
    response = _import_json(
        client,
        {"tasks": [{"project_id": str(uuid4()), "title": "Unknown project task"}]},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_invalid_task_status_is_rejected(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Invalid status project")

    response = _import_json(
        client,
        {
            "tasks": [
                {
                    "project_id": str(project.id),
                    "title": "Invalid status task",
                    "status": "blocked",
                }
            ]
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert db.scalars(select(Task)).all() == []


def test_malformed_json_is_rejected(client: TestClient):
    response = client.post(
        "/api/import",
        files={"file": ("tasks.json", b'{"tasks": [', "application/json")},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_malformed_csv_is_rejected(client: TestClient):
    response = client.post(
        "/api/import",
        files={
            "file": (
                "tasks.csv",
                b'project_id,title\n"unterminated',
                "text/csv",
            )
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_missing_required_import_data_is_rejected(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Missing data project")

    response = _import_json(
        client,
        {"tasks": [{"project_id": str(project.id)}]},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert db.scalars(select(Task)).all() == []


def test_invalid_uuid_and_date_are_rejected(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Invalid values project")
    invalid_payloads = [
        {"tasks": [{"project_id": "not-a-uuid", "title": "Bad UUID"}]},
        {
            "tasks": [
                {
                    "project_id": str(project.id),
                    "title": "Bad date",
                    "due_date": "tomorrow",
                }
            ]
        },
    ]

    for payload in invalid_payloads:
        response = _import_json(client, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert db.scalars(select(Task)).all() == []


def test_unsupported_import_file_type_is_rejected(client: TestClient):
    response = client.post(
        "/api/import",
        files={"file": ("tasks.txt", b"not an import", "text/plain")},
    )

    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


def test_empty_import_is_rejected(client: TestClient):
    response = client.post(
        "/api/import",
        files={"file": ("tasks.json", b"", "application/json")},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_oversized_import_is_rejected(client: TestClient):
    oversized_content = b"x" * (export_import.MAX_IMPORT_SIZE_BYTES + 1)

    response = client.post(
        "/api/import",
        files={"file": ("tasks.json", oversized_content, "application/json")},
    )

    assert response.status_code == 413


def test_database_failure_rolls_back_import(
    client: TestClient,
    db: Session,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    project = _create_project(db, current_user, "Rollback project")
    rollback_spy = MagicMock(wraps=db.rollback)
    monkeypatch.setattr(db, "rollback", rollback_spy)
    monkeypatch.setattr(db, "commit", MagicMock(side_effect=RuntimeError("DB failed")))

    with pytest.raises(RuntimeError, match="DB failed"):
        _import_json(
            client,
            {"tasks": [{"project_id": str(project.id), "title": "Rolled back"}]},
        )

    assert rollback_spy.call_count == 1


def test_critical_validation_error_does_not_partially_import(
    client: TestClient,
    db: Session,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    project = _create_project(db, current_user, "Atomic validation project")
    rollback_spy = MagicMock(wraps=db.rollback)
    monkeypatch.setattr(db, "rollback", rollback_spy)
    payload = {
        "tasks": [
            {"project_id": str(project.id), "title": "Would be valid"},
            {
                "project_id": str(project.id),
                "title": "Invalid second task",
                "status": "invalid",
            },
        ]
    }

    response = _import_json(client, payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert rollback_spy.call_count == 1
    assert db.scalars(select(Task)).all() == []


def test_successful_import_uses_one_commit(
    client: TestClient,
    db: Session,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    project = _create_project(db, current_user, "Single transaction project")
    commit_spy = MagicMock(wraps=db.commit)
    monkeypatch.setattr(db, "commit", commit_spy)

    response = _import_json(
        client,
        {
            "tasks": [
                {"project_id": str(project.id), "title": "First task"},
                {"project_id": str(project.id), "title": "Second task"},
            ]
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert commit_spy.call_count == 1


def _import_json(client: TestClient, payload: dict):
    return client.post(
        "/api/import",
        files={
            "file": (
                "tasks.json",
                json.dumps(payload).encode("utf-8"),
                "application/json",
            )
        },
    )


def _import_csv(client: TestClient, content: str):
    return client.post(
        "/api/import",
        files={"file": ("tasks.csv", content.encode("utf-8"), "text/csv")},
    )


def _csv_import_content(rows: list[dict[str, str]]) -> str:
    fieldnames = (
        "project_id",
        "title",
        "description",
        "status",
        "assignee_id",
        "due_date",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


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


def _create_task(
    db: Session,
    project: Project,
    title: str,
    *,
    description: str | None = None,
    task_status: TaskStatus = TaskStatus.TODO,
    assignee_id=None,
    due_date: date | None = None,
    created_at: datetime | None = None,
) -> Task:
    task_arguments = {
        "project_id": project.id,
        "title": title,
        "description": description,
        "status": task_status,
        "assignee_id": assignee_id,
        "due_date": due_date,
    }
    if created_at is not None:
        task_arguments["created_at"] = created_at
        task_arguments["updated_at"] = created_at

    task = Task(**task_arguments)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task
