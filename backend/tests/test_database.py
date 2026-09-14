from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.models.user import User, UserRole, UserStatus
from app.database import Base


pytestmark = pytest.mark.usefixtures("database")


def _user_values(**overrides: object) -> dict[str, object]:
    identity = uuid4().hex
    values: dict[str, object] = {
        "id": uuid4(),
        "email": f"db-{identity}@example.com",
        "username": f"db_{identity}",
        "display_name": None,
        "password_hash": "$argon2id$test-placeholder",
        "oauth_provider": None,
        "oauth_id": None,
        "role": UserRole.USER,
        "status": UserStatus.ACTIVE,
        "avatar_url": "/static/default-avatar.png",
    }
    values.update(overrides)
    return values


def test_complete_initial_migration_upgrades_and_downgrades(
    database_engine: Engine,
    alembic_config: Config,
) -> None:
    try:
        command.downgrade(alembic_config, "base")
        assert set(inspect(database_engine).get_table_names()) <= {"alembic_version"}

        command.upgrade(alembic_config, "head")
        inspector = inspect(database_engine)
        assert set(inspector.get_table_names()) == {
            "alembic_version", "users", "projects", "project_members", "tasks",
            "notifications", "attachments", "api_keys",
        }
        for table in Base.metadata.sorted_tables:
            assert {column["name"] for column in inspector.get_columns(table.name)} == {
                column.name for column in table.columns
            }
        assert {
            "id",
            "email",
            "password_hash",
            "oauth_provider",
            "oauth_id",
            "username",
            "display_name",
            "role",
            "status",
            "avatar_url",
            "created_at",
            "updated_at",
        } == {column["name"] for column in inspector.get_columns("users")}
    finally:
        command.upgrade(alembic_config, "head")


def test_database_rejects_invalid_authentication_identities(
    database: Engine,
) -> None:
    invalid_identities = (
        {"password_hash": None},
        {
            "password_hash": None,
            "oauth_provider": "google",
            "oauth_id": None,
        },
        {
            "password_hash": None,
            "oauth_provider": None,
            "oauth_id": "orphan-subject",
        },
    )

    for overrides in invalid_identities:
        with database.connect() as connection:
            transaction = connection.begin()
            with pytest.raises(IntegrityError):
                connection.execute(
                    User.__table__.insert().values(_user_values(**overrides))
                )
            transaction.rollback()


def test_database_accepts_an_oauth_only_identity(database: Engine) -> None:
    values = _user_values(
        password_hash=None,
        oauth_provider="google",
        oauth_id="valid-google-subject",
    )

    with database.begin() as connection:
        connection.execute(User.__table__.insert().values(values))


def test_database_enforces_unique_email_username_and_oauth_identity(
    database: Engine,
) -> None:
    unique = uuid4().hex
    first = _user_values(
        email=f"unique-{unique}@example.com",
        username=f"unique_{unique}",
        password_hash=None,
        oauth_provider="google",
        oauth_id=f"subject-{unique}",
    )

    duplicate_cases = [
        _user_values(email=first["email"]),
        _user_values(username=first["username"]),
        _user_values(
            password_hash=None,
            oauth_provider="google",
            oauth_id=first["oauth_id"],
        ),
    ]

    for duplicate in duplicate_cases:
        with database.connect() as connection:
            transaction = connection.begin()
            connection.execute(User.__table__.insert().values(first))
            with pytest.raises(IntegrityError):
                connection.execute(User.__table__.insert().values(duplicate))
            transaction.rollback()


def test_upgrade_head_preserves_populated_complete_schema(
    database_engine: Engine,
    alembic_config: Config,
) -> None:
    # The approved disposable reset replaces the old incremental status migration.
    values = _user_values(role=UserRole.ADMIN, display_name="Preserved admin")
    with database_engine.begin() as connection:
        connection.execute(User.__table__.insert().values(values))

    command.upgrade(alembic_config, "head")
    with database_engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, role::text, status::text, display_name FROM users")
        ).all()
    assert rows == [(values["id"], "admin", "active", "Preserved admin")]


def test_migrated_schema_matches_complete_model_metadata(alembic_config: Config) -> None:
    command.check(alembic_config)


def test_database_enforces_case_insensitive_username_uniqueness(database: Engine) -> None:
    first = _user_values(username="CaseSensitiveSpelling")
    second = _user_values(username="casesensitivespelling")
    with database.begin() as connection:
        connection.execute(User.__table__.insert().values(first))
    with database.begin() as connection:
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(User.__table__.insert().values(second))
