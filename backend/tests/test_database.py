from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect
from sqlalchemy.exc import IntegrityError

from app.models.user import User, UserRole


def _user_values(**overrides: object) -> dict[str, object]:
    identity = uuid4().hex
    values: dict[str, object] = {
        "id": uuid4(),
        "email": f"db-{identity}@example.com",
        "username": f"db_{identity}",
        "password_hash": "$argon2id$test-placeholder",
        "oauth_provider": None,
        "oauth_id": None,
        "role": UserRole.USER,
        "avatar_url": "/static/default-avatar.png",
    }
    values.update(overrides)
    return values


def test_initial_users_migration_upgrades_and_downgrades(
    database_engine: Engine,
    alembic_config: Config,
) -> None:
    try:
        command.downgrade(alembic_config, "base")
        assert "users" not in inspect(database_engine).get_table_names()

        command.upgrade(alembic_config, "head")
        inspector = inspect(database_engine)
        assert "users" in inspector.get_table_names()
        assert {
            "id",
            "email",
            "password_hash",
            "oauth_provider",
            "oauth_id",
            "username",
            "role",
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
