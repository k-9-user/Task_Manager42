from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.models.user import User, UserRole, UserStatus


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


def test_status_migration_repairs_a_populated_database_without_an_admin(
    database_engine: Engine,
    alembic_config: Config,
) -> None:
    first_id = uuid4()
    second_id = uuid4()
    try:
        with database_engine.begin() as connection:
            connection.execute(text("TRUNCATE TABLE users CASCADE"))
        command.downgrade(alembic_config, "db_install")
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (
                        id, email, password_hash, username, role,
                        avatar_url, created_at, updated_at
                    ) VALUES (
                        :first_id, 'legacy-first@example.com', :password_hash,
                        'legacy_first', 'user', '/static/default-avatar.png',
                        '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'
                    ), (
                        :second_id, 'legacy-second@example.com', :password_hash,
                        'legacy_second', 'user', '/static/default-avatar.png',
                        '2026-01-02T00:00:00Z', '2026-01-02T00:00:00Z'
                    )
                    """
                ),
                {
                    "first_id": first_id,
                    "second_id": second_id,
                    "password_hash": "$argon2id$legacy-placeholder",
                },
            )

        command.upgrade(alembic_config, "head")
        with database_engine.connect() as connection:
            roles = connection.execute(
                text("SELECT id, role::text FROM users ORDER BY created_at, id")
            ).all()

        assert roles == [(first_id, "admin"), (second_id, "user")]
    finally:
        command.upgrade(alembic_config, "head")
        with database_engine.begin() as connection:
            connection.execute(text("TRUNCATE TABLE users CASCADE"))
