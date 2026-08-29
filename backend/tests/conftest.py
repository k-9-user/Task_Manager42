import os
from collections.abc import Callable, Generator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")

os.environ["DATABASE_URL"] = (
    TEST_DATABASE_URL
    or "postgresql://taskmanager:taskmanager@127.0.0.1/taskmanager_missing_test"
)
os.environ["JWT_SECRET"] = "test-jwt-signing-secret-at-least-32-characters"
os.environ["JWT_EXPIRATION"] = "3600"
os.environ["OAUTH_GOOGLE_CLIENT_ID"] = "test-google-client"
os.environ["OAUTH_GOOGLE_CLIENT_SECRET"] = "test-google-secret"
os.environ["OAUTH_GOOGLE_REDIRECT_URI"] = (
    "https://testserver/api/auth/oauth/google/callback"
)
os.environ["OAUTH_SESSION_SECRET"] = (
    "test-oauth-session-secret-at-least-32-characters"
)


def _checked_test_database_url() -> str:
    if not TEST_DATABASE_URL:
        pytest.fail(
            "Database/API tests require TEST_DATABASE_URL for a disposable "
            "PostgreSQL database whose name ends in '_test'.",
            pytrace=False,
        )

    url = make_url(TEST_DATABASE_URL)
    if url.get_backend_name() != "postgresql" or not (
        url.database and url.database.endswith("_test")
    ):
        pytest.fail(
            "Refusing database tests: TEST_DATABASE_URL must be PostgreSQL "
            "and its database name must end in '_test'.",
            pytrace=False,
        )
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option(
        "sqlalchemy.url",
        _checked_test_database_url().replace("%", "%%"),
    )
    return config


@pytest.fixture(scope="session")
def database_engine(alembic_config: Config) -> Generator[Engine, None, None]:
    database_url = _checked_test_database_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        command.upgrade(alembic_config, "head")
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.fail(
            "Disposable PostgreSQL test database is not reachable; create it "
            "and rerun with TEST_DATABASE_URL.",
            pytrace=False,
        )

    yield engine
    engine.dispose()


@pytest.fixture
def database(database_engine: Engine) -> Generator[Engine, None, None]:
    with database_engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE users CASCADE"))
    yield database_engine
    with database_engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE users CASCADE"))


@pytest.fixture
def client(database: Engine) -> Generator[TestClient, None, None]:
    from app.main import app

    app.dependency_overrides.clear()
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def user_factory(
    database: Engine,
) -> Callable[..., object]:
    from app.auth.security import hash_password
    from app.database import SessionLocal
    from app.models.user import User, UserRole

    def create_user(
        *,
        email: str | None = None,
        username: str | None = None,
        role: UserRole = UserRole.USER,
        oauth_id: str | None = None,
    ) -> User:
        identity = uuid4().hex
        is_oauth = oauth_id is not None
        user = User(
            email=email or f"user-{identity}@example.com",
            username=username or f"user_{identity}",
            role=role,
            password_hash=None if is_oauth else hash_password("valid-password-42"),
            oauth_provider="google" if is_oauth else None,
            oauth_id=oauth_id,
        )
        with SessionLocal() as session:
            session.add(user)
            session.commit()
            session.refresh(user)
            session.expunge(user)
        return user

    return create_user


@pytest.fixture
def auth_headers() -> Callable[[object], dict[str, str]]:
    from app.auth.security import create_access_token

    def headers(user: object) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return headers
