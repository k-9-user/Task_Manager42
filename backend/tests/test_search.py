from collections.abc import Generator
from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.database import Base, get_db
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.routers import search


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
    return _create_user(db, "search-user")


@pytest.fixture
def app(db: Session, current_user: User) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(search.router)

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_current_user] = lambda: current_user
    return test_app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


def test_router_exposes_exact_search_route():
    routes = {
        (method, route.path)
        for route in search.router.routes
        for method in route.methods
    }

    assert routes == {("GET", "/api/search/tasks")}


def test_openapi_documents_search_parameters_without_api_key(app: FastAPI):
    operation = app.openapi()["paths"]["/api/search/tasks"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert operation["summary"] == "Search accessible tasks"
    assert operation["description"]
    assert set(parameters) == {"q", "status", "project_id", "page", "limit"}
    assert parameters["page"]["schema"]["default"] == 1
    assert parameters["limit"]["schema"]["default"] == 20
    assert "X-API-Key" not in parameters


def test_missing_shared_current_user_dependency_fails_closed(db: Session):
    test_app = FastAPI()
    test_app.include_router(search.router)

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app) as test_client:
        response = test_client.get("/api/search/tasks")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_owner_sees_tasks_from_owned_project(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Owned project")
    task = _create_task(db, project, "Owned task")

    response = client.get("/api/search/tasks")

    assert response.status_code == status.HTTP_200_OK
    assert _task_ids(response) == {str(task.id)}


def test_editor_sees_tasks_from_joined_project(
    client: TestClient,
    db: Session,
    current_user: User,
):
    owner = _create_user(db, "editor-project-owner")
    project = _create_project(db, owner, "Editor project")
    _add_member(db, project, current_user, ProjectRole.EDITOR)
    task = _create_task(db, project, "Editor task")

    response = client.get("/api/search/tasks")

    assert response.status_code == status.HTTP_200_OK
    assert _task_ids(response) == {str(task.id)}


def test_viewer_sees_tasks_from_joined_project(
    client: TestClient,
    db: Session,
    current_user: User,
):
    owner = _create_user(db, "viewer-project-owner")
    project = _create_project(db, owner, "Viewer project")
    _add_member(db, project, current_user, ProjectRole.VIEWER)
    task = _create_task(db, project, "Viewer task")

    response = client.get("/api/search/tasks")

    assert response.status_code == status.HTTP_200_OK
    assert _task_ids(response) == {str(task.id)}


def test_unrelated_users_tasks_are_excluded(
    client: TestClient,
    db: Session,
    current_user: User,
):
    visible_project = _create_project(db, current_user, "Visible project")
    visible_task = _create_task(db, visible_project, "Visible task")
    other_user = _create_user(db, "unrelated-owner")
    private_project = _create_project(db, other_user, "Private project")
    _create_task(db, private_project, "Private task")

    response = client.get("/api/search/tasks")

    assert response.status_code == status.HTTP_200_OK
    assert _task_ids(response) == {str(visible_task.id)}
    assert response.json()["data"]["total"] == 1


def test_q_matches_task_title(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Title search project")
    matching_task = _create_task(db, project, "Release checklist")
    _create_task(db, project, "Unrelated task", description="Nothing relevant")

    response = client.get("/api/search/tasks", params={"q": "checklist"})

    assert _task_ids(response) == {str(matching_task.id)}


def test_q_matches_task_description(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Description search project")
    matching_task = _create_task(
        db,
        project,
        "Generic title",
        description="Prepare the quarterly report",
    )
    _create_task(db, project, "Another task", description="No match")

    response = client.get("/api/search/tasks", params={"q": "quarterly"})

    assert _task_ids(response) == {str(matching_task.id)}


def test_q_search_is_case_insensitive(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Case search project")
    matching_task = _create_task(db, project, "MiXeD CaSe title")

    response = client.get("/api/search/tasks", params={"q": "mixed case"})

    assert _task_ids(response) == {str(matching_task.id)}


def test_whitespace_q_is_treated_as_no_filter(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Whitespace search project")
    first_task = _create_task(db, project, "First task")
    second_task = _create_task(db, project, "Second task")

    response = client.get("/api/search/tasks", params={"q": "   "})

    assert _task_ids(response) == {str(first_task.id), str(second_task.id)}
    assert response.json()["data"]["total"] == 2


@pytest.mark.parametrize(
    "task_status",
    [TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.DONE],
)
def test_status_filters_tasks(
    client: TestClient,
    db: Session,
    current_user: User,
    task_status: TaskStatus,
):
    project = _create_project(db, current_user, f"{task_status.value} project")
    matching_task = _create_task(
        db,
        project,
        f"{task_status.value} task",
        task_status=task_status,
    )
    for other_status in TaskStatus:
        if other_status is not task_status:
            _create_task(
                db,
                project,
                f"Other {other_status.value} task",
                task_status=other_status,
            )

    response = client.get(
        "/api/search/tasks",
        params={"status": task_status.value},
    )

    assert response.status_code == status.HTTP_200_OK
    assert _task_ids(response) == {str(matching_task.id)}


def test_invalid_status_is_rejected(client: TestClient):
    response = client.get("/api/search/tasks", params={"status": "blocked"})

    assert response.status_code == 422


def test_project_id_filters_visible_tasks(
    client: TestClient,
    db: Session,
    current_user: User,
):
    first_project = _create_project(db, current_user, "First project")
    second_project = _create_project(db, current_user, "Second project")
    matching_task = _create_task(db, first_project, "First project task")
    _create_task(db, second_project, "Second project task")

    response = client.get(
        "/api/search/tasks",
        params={"project_id": str(first_project.id)},
    )

    assert _task_ids(response) == {str(matching_task.id)}
    assert response.json()["data"]["total"] == 1


def test_unrelated_project_id_returns_no_results(
    client: TestClient,
    db: Session,
    current_user: User,
):
    other_user = _create_user(db, "private-filter-owner")
    private_project = _create_project(db, other_user, "Private filter project")
    _create_task(db, private_project, "Private filtered task")

    response = client.get(
        "/api/search/tasks",
        params={"project_id": str(private_project.id)},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "success": True,
        "data": {"tasks": [], "total": 0},
    }


def test_default_page_and_limit_return_first_twenty_tasks(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Default pagination project")
    _create_numbered_tasks(db, project, 25)

    response = client.get("/api/search/tasks")

    tasks = response.json()["data"]["tasks"]
    assert response.status_code == status.HTTP_200_OK
    assert len(tasks) == 20
    assert response.json()["data"]["total"] == 25
    assert [task["title"] for task in tasks] == [
        f"Task {number:02d}" for number in range(24, 4, -1)
    ]


def test_page_two_uses_correct_offset(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Second page project")
    _create_numbered_tasks(db, project, 25)

    response = client.get("/api/search/tasks", params={"page": 2})

    tasks = response.json()["data"]["tasks"]
    assert response.status_code == status.HTTP_200_OK
    assert [task["title"] for task in tasks] == [
        f"Task {number:02d}" for number in range(4, -1, -1)
    ]


def test_custom_limit_controls_page_size(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Custom limit project")
    _create_numbered_tasks(db, project, 15)

    response = client.get("/api/search/tasks", params={"limit": 7})

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["data"]["tasks"]) == 7
    assert response.json()["data"]["total"] == 15


def test_total_is_calculated_before_pagination(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Total pagination project")
    _create_numbered_tasks(db, project, 12)

    response = client.get(
        "/api/search/tasks",
        params={"page": 2, "limit": 5},
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["data"]["tasks"]) == 5
    assert response.json()["data"]["total"] == 12


def test_invalid_page_is_rejected(client: TestClient):
    response = client.get("/api/search/tasks", params={"page": 0})

    assert response.status_code == 422


def test_invalid_limit_is_rejected(client: TestClient):
    response = client.get("/api/search/tasks", params={"limit": 0})

    assert response.status_code == 422


def test_limit_above_one_hundred_is_rejected(client: TestClient):
    response = client.get("/api/search/tasks", params={"limit": 101})

    assert response.status_code == 422


def test_empty_response_uses_standard_contract(client: TestClient):
    response = client.get("/api/search/tasks")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "success": True,
        "data": {"tasks": [], "total": 0},
    }


def test_task_response_contains_only_public_task_fields(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Serialization project")
    created_at = datetime(2026, 1, 2, 3, 4, 5)
    task = _create_task(
        db,
        project,
        "Serialized task",
        description="Serialized description",
        task_status=TaskStatus.DONE,
        assignee_id=current_user.id,
        due_date=date(2026, 2, 3),
        created_at=created_at,
    )

    response = client.get("/api/search/tasks")

    assert response.json()["data"]["tasks"] == [
        {
            "id": str(task.id),
            "project_id": str(project.id),
            "title": "Serialized task",
            "description": "Serialized description",
            "status": "done",
            "assignee_id": str(current_user.id),
            "due_date": "2026-02-03",
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
        }
    ]


def test_visibility_is_applied_before_pagination(
    client: TestClient,
    db: Session,
    current_user: User,
):
    visible_project = _create_project(db, current_user, "Visible pagination project")
    visible_tasks = _create_numbered_tasks(db, visible_project, 3)
    other_user = _create_user(db, "pagination-private-owner")
    private_project = _create_project(db, other_user, "Private pagination project")
    _create_numbered_tasks(db, private_project, 25, start_day=10)

    response = client.get("/api/search/tasks")

    assert response.status_code == status.HTTP_200_OK
    assert _task_ids(response) == {str(task.id) for task in visible_tasks}
    assert response.json()["data"]["total"] == 3


def test_results_are_sorted_by_created_at_descending(
    client: TestClient,
    db: Session,
    current_user: User,
):
    project = _create_project(db, current_user, "Sorting project")
    _create_numbered_tasks(db, project, 3)

    response = client.get("/api/search/tasks")

    assert [task["title"] for task in response.json()["data"]["tasks"]] == [
        "Task 02",
        "Task 01",
        "Task 00",
    ]


def _task_ids(response) -> set[str]:
    return {task["id"] for task in response.json()["data"]["tasks"]}


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


def _create_numbered_tasks(
    db: Session,
    project: Project,
    count: int,
    *,
    start_day: int = 1,
) -> list[Task]:
    base_time = datetime(2026, 1, start_day)
    tasks = [
        Task(
            project_id=project.id,
            title=f"Task {number:02d}",
            created_at=base_time + timedelta(minutes=number),
            updated_at=base_time + timedelta(minutes=number),
        )
        for number in range(count)
    ]
    db.add_all(tasks)
    db.commit()
    return tasks
