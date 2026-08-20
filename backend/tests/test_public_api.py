from collections.abc import Generator
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.api_key import ApiKey
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.routers import public_api
from app.utils.rate_limiter import ApiKeyRateLimiter


VALID_API_KEY = "valid-public-api-test-key"


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
def app(db: Session) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(public_api.router)

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def limiter(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    limiter_mock = MagicMock(spec=ApiKeyRateLimiter)
    monkeypatch.setattr(public_api, "rate_limiter", limiter_mock)
    return limiter_mock


@pytest.fixture
def api_user(db: Session) -> User:
    user = _create_user(db, "api-user")
    db.add(ApiKey(user_id=user.id, key=VALID_API_KEY))
    db.commit()
    return user


def test_router_exposes_exact_public_contract_routes():
    routes = {
        (method, route.path)
        for route in public_api.router.routes
        for method in route.methods
    }

    assert routes == {
        ("GET", "/api/v1/public/tasks"),
        ("POST", "/api/v1/public/tasks"),
        ("PUT", "/api/v1/public/tasks/{task_id}"),
        ("DELETE", "/api/v1/public/tasks/{task_id}"),
        ("GET", "/api/v1/public/projects"),
    }


def test_openapi_documents_operations_schemas_and_api_key(app: FastAPI):
    schema = app.openapi()
    operations = [
        schema["paths"]["/api/v1/public/tasks"]["get"],
        schema["paths"]["/api/v1/public/tasks"]["post"],
        schema["paths"]["/api/v1/public/tasks/{task_id}"]["put"],
        schema["paths"]["/api/v1/public/tasks/{task_id}"]["delete"],
        schema["paths"]["/api/v1/public/projects"]["get"],
    ]

    for operation in operations:
        assert operation["summary"]
        assert operation["description"]
        api_key_parameters = [
            parameter
            for parameter in operation["parameters"]
            if parameter["in"] == "header" and parameter["name"] == "X-API-Key"
        ]
        assert len(api_key_parameters) == 1
        assert api_key_parameters[0]["required"] is True

    assert "PublicTaskCreate" in schema["components"]["schemas"]
    assert "PublicTaskUpdate" in schema["components"]["schemas"]


def test_missing_api_key_is_rejected(client: TestClient):
    response = client.get("/api/v1/public/projects")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_invalid_api_key_is_rejected(client: TestClient):
    response = client.get(
        "/api/v1/public/projects",
        headers=_headers("invalid-public-api-key"),
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize(
    ("method", "path", "payload", "expected_status"),
    [
        ("GET", "/api/v1/public/tasks", None, status.HTTP_200_OK),
        (
            "POST",
            "/api/v1/public/tasks",
            {"project_id": str(uuid4()), "title": "Task"},
            status.HTTP_404_NOT_FOUND,
        ),
        (
            "PUT",
            f"/api/v1/public/tasks/{uuid4()}",
            {"status": "done"},
            status.HTTP_404_NOT_FOUND,
        ),
        (
            "DELETE",
            f"/api/v1/public/tasks/{uuid4()}",
            None,
            status.HTTP_404_NOT_FOUND,
        ),
        ("GET", "/api/v1/public/projects", None, status.HTTP_200_OK),
    ],
)
def test_every_public_route_invokes_rate_limiter(
    client: TestClient,
    api_user: User,
    limiter: MagicMock,
    method: str,
    path: str,
    payload: dict | None,
    expected_status: int,
):
    request_arguments = {"headers": _headers()}
    if payload is not None:
        request_arguments["json"] = payload

    response = client.request(method, path, **request_arguments)

    assert response.status_code == expected_status
    limiter.check.assert_called_once_with(VALID_API_KEY)


def test_rate_limit_exception_propagates_as_429(
    client: TestClient,
    api_user: User,
    limiter: MagicMock,
):
    limiter.check.side_effect = HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded",
    )

    response = client.get("/api/v1/public/projects", headers=_headers())

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.json() == {"detail": "Rate limit exceeded"}


def test_project_owner_sees_owned_project(
    client: TestClient,
    db: Session,
    api_user: User,
):
    project = _create_project(db, api_user, "Owned project")

    response = client.get("/api/v1/public/projects", headers=_headers())

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "success": True,
        "data": {
            "projects": [
                {
                    "id": str(project.id),
                    "name": "Owned project",
                    "description": None,
                    "owner_id": str(api_user.id),
                    "created_at": project.created_at.isoformat(),
                }
            ]
        },
    }


def test_project_member_sees_joined_project(
    client: TestClient,
    db: Session,
    api_user: User,
):
    other_user = _create_user(db, "joined-project-owner")
    project = _create_project(db, other_user, "Joined project")
    _add_member(db, project, api_user, ProjectRole.VIEWER)

    response = client.get("/api/v1/public/projects", headers=_headers())

    assert response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in response.json()["data"]["projects"]] == [
        str(project.id)
    ]


def test_unrelated_project_is_excluded(
    client: TestClient,
    db: Session,
    api_user: User,
):
    visible_project = _create_project(db, api_user, "Visible project")
    other_user = _create_user(db, "unrelated-project-owner")
    _create_project(db, other_user, "Private project")

    response = client.get("/api/v1/public/projects", headers=_headers())

    project_ids = {item["id"] for item in response.json()["data"]["projects"]}
    assert response.status_code == status.HTTP_200_OK
    assert project_ids == {str(visible_project.id)}


def test_accessible_task_is_returned(
    client: TestClient,
    db: Session,
    api_user: User,
):
    project = _create_project(db, api_user, "Task project")
    task = _create_task(db, project, "Visible task")

    response = client.get("/api/v1/public/tasks", headers=_headers())

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True
    assert response.json()["data"]["tasks"] == [
        {
            "id": str(task.id),
            "project_id": str(project.id),
            "title": "Visible task",
            "description": None,
            "status": "todo",
            "assignee_id": None,
            "due_date": None,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        }
    ]


def test_unrelated_task_is_excluded(
    client: TestClient,
    db: Session,
    api_user: User,
):
    visible_project = _create_project(db, api_user, "Visible task project")
    visible_task = _create_task(db, visible_project, "Visible task")
    other_user = _create_user(db, "unrelated-task-owner")
    private_project = _create_project(db, other_user, "Private task project")
    _create_task(db, private_project, "Private task")

    response = client.get("/api/v1/public/tasks", headers=_headers())

    task_ids = {item["id"] for item in response.json()["data"]["tasks"]}
    assert response.status_code == status.HTTP_200_OK
    assert task_ids == {str(visible_task.id)}


def test_viewer_can_read_tasks(
    client: TestClient,
    db: Session,
    api_user: User,
):
    other_user = _create_user(db, "viewer-project-owner")
    project = _create_project(db, other_user, "Viewer project")
    _add_member(db, project, api_user, ProjectRole.VIEWER)
    task = _create_task(db, project, "Viewer-readable task")

    response = client.get("/api/v1/public/tasks", headers=_headers())

    assert response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in response.json()["data"]["tasks"]] == [
        str(task.id)
    ]


def test_project_owner_can_create_task(
    client: TestClient,
    db: Session,
    api_user: User,
):
    project = _create_project(db, api_user, "Owner write project")

    response = client.post(
        "/api/v1/public/tasks",
        headers=_headers(),
        json={"project_id": str(project.id), "title": "Owner task"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True
    assert response.json()["data"]["task"]["title"] == "Owner task"
    assert response.json()["data"]["task"]["status"] == "todo"


def test_editor_can_create_task(
    client: TestClient,
    db: Session,
    api_user: User,
):
    other_user = _create_user(db, "editor-project-owner")
    project = _create_project(db, other_user, "Editor write project")
    _add_member(db, project, api_user, ProjectRole.EDITOR)

    response = client.post(
        "/api/v1/public/tasks",
        headers=_headers(),
        json={"project_id": str(project.id), "title": "Editor task"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["task"]["title"] == "Editor task"


def test_viewer_cannot_create_task(
    client: TestClient,
    db: Session,
    api_user: User,
):
    other_user = _create_user(db, "viewer-write-owner")
    project = _create_project(db, other_user, "Viewer write project")
    _add_member(db, project, api_user, ProjectRole.VIEWER)

    response = client.post(
        "/api/v1/public/tasks",
        headers=_headers(),
        json={"project_id": str(project.id), "title": "Forbidden task"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert db.scalars(select(Task)).all() == []


def test_unrelated_project_is_not_accessible_for_creation(
    client: TestClient,
    db: Session,
    api_user: User,
):
    other_user = _create_user(db, "private-create-owner")
    project = _create_project(db, other_user, "Private create project")

    response = client.post(
        "/api/v1/public/tasks",
        headers=_headers(),
        json={"project_id": str(project.id), "title": "Hidden task"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("title", ["", "   "])
def test_empty_title_is_rejected(
    client: TestClient,
    db: Session,
    api_user: User,
    title: str,
):
    project = _create_project(db, api_user, "Title validation project")

    response = client.post(
        "/api/v1/public/tasks",
        headers=_headers(),
        json={"project_id": str(project.id), "title": title},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.parametrize("access", ["owner", "editor"])
def test_owner_or_editor_can_update_valid_status(
    client: TestClient,
    db: Session,
    api_user: User,
    access: str,
):
    project = _create_project_for_access(db, api_user, access, "Update")
    task = _create_task(db, project, "Task to update")

    response = client.put(
        f"/api/v1/public/tasks/{task.id}",
        headers=_headers(),
        json={"status": "done"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True
    assert response.json()["data"]["task"]["status"] == "done"
    db.refresh(task)
    assert task.status is TaskStatus.DONE


def test_viewer_cannot_update_task(
    client: TestClient,
    db: Session,
    api_user: User,
):
    project = _create_project_for_access(db, api_user, "viewer", "Viewer update")
    task = _create_task(db, project, "Viewer cannot update")

    response = client.put(
        f"/api/v1/public/tasks/{task.id}",
        headers=_headers(),
        json={"status": "done"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    db.refresh(task)
    assert task.status is TaskStatus.TODO


def test_invalid_status_is_rejected(
    client: TestClient,
    db: Session,
    api_user: User,
):
    project = _create_project(db, api_user, "Status validation project")
    task = _create_task(db, project, "Status validation task")

    response = client.put(
        f"/api/v1/public/tasks/{task.id}",
        headers=_headers(),
        json={"status": "blocked"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_unrelated_task_returns_404_for_update(
    client: TestClient,
    db: Session,
    api_user: User,
):
    other_user = _create_user(db, "private-update-owner")
    project = _create_project(db, other_user, "Private update project")
    task = _create_task(db, project, "Private update task")

    response = client.put(
        f"/api/v1/public/tasks/{task.id}",
        headers=_headers(),
        json={"status": "done"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_optional_status_may_be_omitted(
    client: TestClient,
    db: Session,
    api_user: User,
):
    project = _create_project(db, api_user, "Optional update project")
    task = _create_task(db, project, "Unchanged task")

    response = client.put(
        f"/api/v1/public/tasks/{task.id}",
        headers=_headers(),
        json={},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["task"]["status"] == "todo"


@pytest.mark.parametrize("access", ["owner", "editor"])
def test_owner_or_editor_can_delete_task(
    client: TestClient,
    db: Session,
    api_user: User,
    access: str,
):
    project = _create_project_for_access(db, api_user, access, "Delete")
    task = _create_task(db, project, "Task to delete")
    task_id = task.id

    response = client.delete(
        f"/api/v1/public/tasks/{task_id}",
        headers=_headers(),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"success": True, "data": {"success": True}}
    assert db.get(Task, task_id) is None


def test_viewer_cannot_delete_task(
    client: TestClient,
    db: Session,
    api_user: User,
):
    project = _create_project_for_access(db, api_user, "viewer", "Viewer delete")
    task = _create_task(db, project, "Viewer cannot delete")

    response = client.delete(
        f"/api/v1/public/tasks/{task.id}",
        headers=_headers(),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert db.get(Task, task.id) is not None


def test_unrelated_task_returns_404_for_delete(
    client: TestClient,
    db: Session,
    api_user: User,
):
    other_user = _create_user(db, "private-delete-owner")
    project = _create_project(db, other_user, "Private delete project")
    task = _create_task(db, project, "Private delete task")

    response = client.delete(
        f"/api/v1/public/tasks/{task.id}",
        headers=_headers(),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert db.get(Task, task.id) is not None


def _headers(api_key: str = VALID_API_KEY) -> dict[str, str]:
    return {"X-API-Key": api_key}


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


def _create_project_for_access(
    db: Session,
    api_user: User,
    access: str,
    action: str,
) -> Project:
    if access == "owner":
        return _create_project(db, api_user, f"{action} owner project")

    other_user = _create_user(db, f"{action.lower()}-project-owner")
    project = _create_project(db, other_user, f"{action} member project")
    role = ProjectRole.EDITOR if access == "editor" else ProjectRole.VIEWER
    _add_member(db, project, api_user, role)
    return project
