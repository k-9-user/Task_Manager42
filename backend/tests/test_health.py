from collections.abc import Generator
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app


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
