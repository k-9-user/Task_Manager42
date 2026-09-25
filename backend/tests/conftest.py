"""Shared setup: the throwaway PostgreSQL started by `make test`, the real app, real HTTP calls."""

import os
import secrets
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

assert os.environ.get("DATABASE_URL", "").endswith("/taskmanager_test"), "run the tests with make test"
os.environ.update(
    JWT_SECRET=secrets.token_urlsafe(32),
    OAUTH_SESSION_SECRET=secrets.token_urlsafe(32),
    PASSWORD_MIN_LENGTH="8",
    PASSWORD_MAX_LENGTH="128",
    UPLOAD_DIR="/tmp/test-uploads",
    MAX_UPLOAD_SIZE_MB="1",
)

from app.main import app  # noqa: E402  (the settings above must exist before the app loads)


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


@pytest.fixture(scope="session", autouse=True)
def migrated_database(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture(scope="session")
def password() -> str:
    return secrets.token_urlsafe(12)


@pytest.fixture
def signup(client, password):
    """Register a new user through the API; return the user and its auth headers."""

    def register():
        name = f"user_{uuid4().hex[:12]}"
        response = client.post(
            "/api/auth/register",
            json={"email": f"{name}@example.com", "username": name, "password": password},
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        return data["user"], {"Authorization": f"Bearer {data['token']}"}

    return register


@pytest.fixture
def create_project(client):
    def create(headers, name="Project"):
        response = client.post("/api/projects", headers=headers, json={"name": name})
        assert response.status_code == 201, response.text
        return response.json()["data"]["project"]

    return create


@pytest.fixture
def create_task(client):
    def create(headers, project, title="Task", **fields):
        response = client.post(
            f"/api/projects/{project['id']}/tasks", headers=headers, json={"title": title, **fields}
        )
        assert response.status_code == 201, response.text
        return response.json()["data"]["task"]

    return create
