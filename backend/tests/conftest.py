"""Real-app integration fixtures; unit/SQLite tests never request PostgreSQL DDL."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from tests.database_safety import validate_test_database_url


# Configure before importing app.database or any test module. Never inherit a dev DB.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    test_url = validate_test_database_url(TEST_DATABASE_URL)
    configured_url = os.environ.get("DATABASE_URL")
    if configured_url and make_url(configured_url) != test_url:
        raise ValueError("DATABASE_URL and TEST_DATABASE_URL must match for tests")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL or "sqlite+pysqlite:///:memory:"
os.environ.update(
    JWT_SECRET="test-jwt-signing-secret-not-for-deployment-42",
    OAUTH_SESSION_SECRET="test-oauth-signing-secret-not-for-deployment-42",
    JWT_EXPIRATION="3600",
    CORS_ORIGINS="https://localhost:8443",
    OAUTH_GOOGLE_CLIENT_ID="test-google-client",
    OAUTH_GOOGLE_CLIENT_SECRET="test-google-secret",
    OAUTH_GOOGLE_REDIRECT_URI="https://testserver/api/auth/oauth/google/callback",
)

from app.auth.dependencies import get_current_user
from app.auth.security import create_access_token, hash_password
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.api_key import ApiKey
from app.models.attachment import Attachment
from app.models.notification import Notification
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.user import User


@pytest.fixture(autouse=True)
def isolated_app_overrides():
    previous = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


@pytest.fixture(scope="session")
def alembic_config():
    url = validate_test_database_url(TEST_DATABASE_URL)
    if engine.url != url:
        raise ValueError("Application engine must use the guarded test database")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%"))
    return config


@pytest.fixture(scope="session")
def database_engine(alembic_config):
    # The guard above runs before Alembic can connect or execute DDL.
    command.upgrade(alembic_config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def database(database_engine):
    validate_test_database_url(database_engine.url.render_as_string(hide_password=False))
    tables = ", ".join(
        database_engine.dialect.identifier_preparer.quote(table.name)
        for table in Base.metadata.sorted_tables
    )
    # Committed rows are needed by A's concurrent requests and independent sessions.
    with database_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    try:
        yield database_engine
    finally:
        with database_engine.begin() as connection:
            connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db_session(database):
    with SessionLocal() as session:
        yield session


@pytest.fixture(scope="session")
def password_hash():
    return hash_password("valid-password-42")


@pytest.fixture
def user_factory(database, password_hash):
    def create(**overrides):
        suffix = uuid4().hex
        values = {
            "email": f"user-{suffix}@example.com",
            "username": f"user_{suffix}",
            "password_hash": password_hash,
        }
        if overrides.get("oauth_id") is not None:
            values.update(oauth_provider="google", password_hash=None)
        values.update(overrides)
        with SessionLocal() as session:
            user = User(**values)
            session.add(user)
            session.commit()
            session.refresh(user)
            session.expunge(user)
            return user
    return create


@pytest.fixture
def make_user(user_factory):
    def create(email=None, username=None):
        return user_factory(**{
            key: value for key, value in {"email": email, "username": username}.items()
            if value is not None
        })
    return create


@pytest.fixture
def auth_headers():
    return lambda user: {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.fixture
def client(database):
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def member_client(database, make_user):
    """B's explicit identity override, on the same real app used by A."""
    current_user = make_user()
    app.dependency_overrides[get_current_user] = lambda: current_user
    with TestClient(app, base_url="https://testserver") as test_client:
        test_client.current_user = current_user
        yield test_client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def login_as(client):
    def login(user):
        app.dependency_overrides[get_current_user] = lambda: user
        client.current_user = user
    return login
