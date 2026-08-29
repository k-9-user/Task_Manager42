from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy import func, select

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password_and_update,
)
from app.database import SessionLocal
from app.main import app
from app.models.user import User, UserRole
from app.schemas.user import UserRegister, UserUpdate


VALID_REGISTRATION = {
    "email": "first@example.com",
    "username": "first_user",
    "password": "valid-password",
}


def test_password_hashing_and_equalized_verification() -> None:
    password_hash = hash_password("valid-password")

    assert password_hash.startswith("$argon2id$")
    assert verify_password_and_update("valid-password", password_hash)[0]
    assert not verify_password_and_update("wrong-password", password_hash)[0]
    assert verify_password_and_update("valid-password", None) == (False, None)
    assert verify_password_and_update("dummy-password-equalizer", "") == (
        False,
        None,
    )
    assert verify_password_and_update("valid-password", "not-a-hash") == (
        False,
        None,
    )


def test_access_tokens_round_trip_and_reject_invalid_values() -> None:
    user_id = uuid4()
    token = create_access_token(user_id)

    assert decode_access_token(token) == user_id
    invalid_tokens = (
        "not-a-jwt",
        create_access_token(
            "00000000-0000-0000-0000-000000000001",
            expires_delta=timedelta(seconds=-1),
        ),
    )
    for invalid_token in invalid_tokens:
        with pytest.raises(InvalidTokenError):
            decode_access_token(invalid_token)


def test_registration_schema_is_strict() -> None:
    invalid_payloads = (
        {**VALID_REGISTRATION, "password": "too-short"},
        {**VALID_REGISTRATION, "username": "spaces are invalid"},
        {**VALID_REGISTRATION, "unexpected": True},
    )
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            UserRegister.model_validate(payload)


def test_profile_schema_rejects_unsafe_local_avatar_paths() -> None:
    for avatar in ("/../admin", "/avatars/../../private.png"):
        with pytest.raises(ValidationError):
            UserUpdate.model_validate({"avatar": avatar})


def test_cors_allows_configured_frontend_preflight() -> None:
    with TestClient(app, base_url="https://testserver") as test_client:
        response = test_client.options(
            "/api/auth/login",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        denied = test_client.options(
            "/api/auth/login",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )
    assert "authorization" in response.headers[
        "access-control-allow-headers"
    ].lower()
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_registration_bootstraps_exactly_one_admin(client: TestClient) -> None:
    first = client.post("/api/auth/register", json=VALID_REGISTRATION)
    second = client.post(
        "/api/auth/register",
        json={
            "email": "second@example.com",
            "username": "second_user",
            "password": "valid-password",
        },
    )

    assert first.status_code == 201
    assert first.json()["data"]["user"]["role"] == "admin"
    assert second.status_code == 201
    assert second.json()["data"]["user"]["role"] == "user"


def test_concurrent_registration_creates_one_admin(database: object) -> None:
    barrier = Barrier(2)

    def register(index: int) -> int:
        barrier.wait()
        with TestClient(app, base_url="https://testserver") as test_client:
            response = test_client.post(
                "/api/auth/register",
                json={
                    "email": f"race-{index}@example.com",
                    "username": f"race_{index}",
                    "password": "valid-password",
                },
            )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(register, (1, 2)))

    with SessionLocal() as session:
        admin_count = session.scalar(
            select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)
        )
        user_count = session.scalar(select(func.count()).select_from(User))

    assert statuses == [201, 201]
    assert admin_count == 1
    assert user_count == 2


def test_duplicate_registration_returns_conflict(client: TestClient) -> None:
    assert client.post("/api/auth/register", json=VALID_REGISTRATION).status_code == 201

    duplicate_email = client.post(
        "/api/auth/register",
        json={**VALID_REGISTRATION, "username": "another_name"},
    )
    duplicate_username = client.post(
        "/api/auth/register",
        json={**VALID_REGISTRATION, "email": "another@example.com"},
    )

    assert duplicate_email.status_code == 409
    assert duplicate_email.json() == {
        "success": False,
        "error": "Email already registered",
    }
    assert duplicate_username.status_code == 409
    assert duplicate_username.json()["error"] == "Username already taken"


def test_login_failure_is_generic_for_unknown_email_and_wrong_password(
    client: TestClient,
) -> None:
    assert client.post("/api/auth/register", json=VALID_REGISTRATION).status_code == 201

    wrong_password = client.post(
        "/api/auth/login",
        json={"email": "first@example.com", "password": "wrong-password"},
    )
    unknown_email = client.post(
        "/api/auth/login",
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {
        "success": False,
        "error": "Invalid email or password",
    }


def test_successful_login_returns_a_usable_token(client: TestClient) -> None:
    registration = client.post("/api/auth/register", json=VALID_REGISTRATION)

    response = client.post(
        "/api/auth/login",
        json={
            "email": VALID_REGISTRATION["email"],
            "password": VALID_REGISTRATION["password"],
        },
    )

    assert response.status_code == 200
    registered_user = registration.json()["data"]["user"]
    assert response.json()["data"]["user"]["id"] == registered_user["id"]
    token = response.json()["data"]["token"]
    current_user = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert current_user.status_code == 200


def test_current_user_rejects_invalid_or_orphaned_tokens(client: TestClient) -> None:
    invalid_headers = (
        {},
        {"Authorization": "Bearer not-a-jwt"},
        {
            "Authorization": "Bearer "
            + create_access_token(uuid4(), expires_delta=timedelta(seconds=-1))
        },
        {"Authorization": "Bearer " + create_access_token(uuid4())},
    )

    for headers in invalid_headers:
        response = client.get("/api/users/me", headers=headers)

        assert response.status_code == 401
        assert response.json()["success"] is False


def test_me_can_be_read_and_updated_without_role_escalation(
    client: TestClient,
) -> None:
    registration = client.post("/api/auth/register", json=VALID_REGISTRATION)
    token = registration.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    current = client.get("/api/users/me", headers=headers)
    updated = client.put(
        "/api/users/me",
        headers=headers,
        json={"username": "renamed_user", "avatar": "/avatars/user.png"},
    )
    escalation = client.put(
        "/api/users/me",
        headers=headers,
        json={"role": "admin"},
    )

    assert current.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["data"]["user"]["username"] == "renamed_user"
    assert updated.json()["data"]["user"]["avatar_url"] == "/avatars/user.png"
    assert escalation.status_code == 422


def test_profile_update_rejects_a_duplicate_username(client: TestClient) -> None:
    first = client.post("/api/auth/register", json=VALID_REGISTRATION)
    client.post(
        "/api/auth/register",
        json={
            "email": "second@example.com",
            "username": "second_user",
            "password": "valid-password",
        },
    )
    headers = {"Authorization": f"Bearer {first.json()['data']['token']}"}

    response = client.put(
        "/api/users/me",
        headers=headers,
        json={"username": "second_user"},
    )

    assert response.status_code == 409
    current_user = client.get("/api/users/me", headers=headers)
    assert current_user.json()["data"]["user"]["username"] == "first_user"
