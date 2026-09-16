"""Deterministic administrator bootstrap against the real test database."""

from sqlalchemy import func, select

from app.auth.security import hash_password, verify_password_and_update
from app.bootstrap_admin import BootstrapError, bootstrap_admin
from app.config import BootstrapSettings
from app.models.user import User, UserRole, UserStatus


ADMIN_PASSWORD = "bootstrap-password-42"


def _settings(**overrides: object) -> BootstrapSettings:
    values = {
        "database_url": "sqlite+pysqlite:///:memory:",
        "bootstrap_admin_email": "admin@example.com",
        "bootstrap_admin_username": "admin",
        "bootstrap_admin_password": ADMIN_PASSWORD,
    }
    values.update(overrides)
    return BootstrapSettings(**values)


def test_empty_database_creates_one_active_admin(db_session) -> None:
    admin = bootstrap_admin(db_session, _settings())

    assert admin.email == "admin@example.com"
    assert admin.username == "admin"
    assert admin.role == UserRole.ADMIN
    assert admin.status == UserStatus.ACTIVE
    password_matches, _updated_hash = verify_password_and_update(
        ADMIN_PASSWORD,
        admin.password_hash,
    )
    assert password_matches is True


def test_bootstrap_is_idempotent_when_first_admin_and_password_match(db_session) -> None:
    first = bootstrap_admin(db_session, _settings())
    second = bootstrap_admin(db_session, _settings())

    assert second.id == first.id
    assert db_session.scalar(select(func.count()).select_from(User)) == 1


def test_matching_existing_first_admin_is_preserved(db_session) -> None:
    existing = User(
        email="admin@example.com",
        username="admin",
        password_hash=hash_password(ADMIN_PASSWORD),
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    db_session.add(existing)
    db_session.commit()
    original_hash = existing.password_hash

    returned = bootstrap_admin(db_session, _settings())

    assert returned.id == existing.id
    assert returned.password_hash == original_hash


def test_nonempty_incompatible_database_fails_without_mutation(db_session) -> None:
    existing = User(
        email="legacy@example.com",
        username="legacy_admin",
        password_hash=hash_password("legacy-password-42"),
        role=UserRole.ADMIN,
    )
    db_session.add(existing)
    db_session.commit()

    try:
        bootstrap_admin(db_session, _settings())
    except BootstrapError as error:
        assert "reset-db" in str(error)
        assert ADMIN_PASSWORD not in str(error)
    else:
        raise AssertionError("incompatible database was accepted")

    db_session.expire_all()
    preserved = db_session.get(User, existing.id)
    assert preserved is not None
    assert preserved.email == "legacy@example.com"
    assert db_session.scalar(select(func.count()).select_from(User)) == 1


def test_matching_identity_with_wrong_role_status_or_password_fails(db_session) -> None:
    cases = (
        {"role": UserRole.USER},
        {"status": UserStatus.BANNED},
        {"password_hash": hash_password("different-password-42")},
    )
    for index, override in enumerate(cases):
        user = User(**({
            "email": "admin@example.com",
            "username": "admin",
            "password_hash": hash_password(ADMIN_PASSWORD),
            "role": UserRole.ADMIN,
            "status": UserStatus.ACTIVE,
        } | override))
        db_session.add(user)
        db_session.commit()

        try:
            bootstrap_admin(db_session, _settings())
        except BootstrapError:
            pass
        else:
            raise AssertionError(f"invalid bootstrap state {index} was accepted")

        db_session.delete(user)
        db_session.commit()
