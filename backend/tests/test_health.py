import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app
from app.routers.health import get_backup_status_file


class UnavailableDatabase:
    def execute(self, _statement: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("database offline"))


def unavailable_database() -> Generator[UnavailableDatabase, None, None]:
    yield UnavailableDatabase()


def test_health_reports_database_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_health_database_failure_is_generic() -> None:
    app.dependency_overrides[get_db] = unavailable_database
    try:
        with TestClient(app, base_url="https://testserver") as test_client:
            response = test_client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "error": "Database unavailable",
    }


def iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def status_file(tmp_path: Path) -> Path:
    path = tmp_path / "status.json"
    app.dependency_overrides[get_backup_status_file] = lambda: path
    return path


def record_backup(path: Path, *, age: timedelta | None, failure_age: timedelta | None = None) -> None:
    now = datetime.now(UTC)
    path.write_text(json.dumps({
        "last_success_at": None if age is None else iso(now - age),
        "last_backup": None if age is None else "taskmanager-20260923T170000Z",
        "count": 0 if age is None else 3,
        "interval_minutes": 60,
        "last_failure_at": None if failure_age is None else iso(now - failure_age),
    }))


def test_status_reports_every_component_ok(client: TestClient, status_file: Path) -> None:
    record_backup(status_file, age=timedelta(minutes=5))

    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["api"] == "ok"
    assert body["database"] == "ok"
    assert body["backups"]["state"] == "ok"
    assert body["backups"]["count"] == 3
    assert body["backups"]["interval_minutes"] == 60
    assert body["backups"]["last_success_at"] is not None
    assert body["checked_at"]


@pytest.mark.parametrize(
    ("age", "failure_age", "state"),
    [
        (timedelta(minutes=121), None, "stale"),
        (timedelta(minutes=30), timedelta(minutes=1), "failing"),
        (None, timedelta(minutes=1), "failing"),
        (None, None, "missing"),
        (timedelta(minutes=5), timedelta(minutes=30), "ok"),
    ],
)
def test_status_grades_backup_freshness(
    client: TestClient,
    status_file: Path,
    age: timedelta | None,
    failure_age: timedelta | None,
    state: str,
) -> None:
    record_backup(status_file, age=age, failure_age=failure_age)

    body = client.get("/api/status").json()

    assert body["backups"]["state"] == state
    assert body["status"] == ("ok" if state == "ok" else "degraded")


@pytest.mark.parametrize(
    "contents",
    [None, "not json", "[]", '{"count": 1}',
     '{"last_success_at": "2026-09-23T17:00:00", "count": 1, "interval_minutes": 60, "last_failure_at": null}'],
)
def test_status_treats_absent_or_malformed_status_as_missing(
    client: TestClient,
    status_file: Path,
    contents: str | None,
) -> None:
    if contents is not None:
        status_file.write_text(contents)

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["backups"] == {
        "state": "missing",
        "last_success_at": None,
        "count": 0,
        "interval_minutes": None,
    }
    assert response.json()["status"] == "degraded"


def test_status_reports_database_down_without_failing(tmp_path: Path) -> None:
    path = tmp_path / "status.json"
    record_backup(path, age=timedelta(minutes=5))
    app.dependency_overrides[get_db] = unavailable_database
    app.dependency_overrides[get_backup_status_file] = lambda: path
    with TestClient(app, base_url="https://testserver") as test_client:
        response = test_client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["database"] == "down"
    assert response.json()["backups"]["state"] == "ok"
    assert response.json()["status"] == "degraded"
