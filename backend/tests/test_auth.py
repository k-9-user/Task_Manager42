from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from typing import Any
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
from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models.user import User, UserRole, UserStatus
from app.schemas.user import (
    UserLogin,
    UserRegister,
    UserStatusUpdate,
    UserUpdate,
)


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


def test_password_with_injection_metacharacters_remains_opaque(
    client: TestClient,
    db_session,
    caplog,
) -> None:
    password = "' OR 1=1 --; $(touch /tmp/injected) <script>"
    registration = client.post(
        "/api/auth/register",
        json={
            "email": "opaque-password@example.com",
            "username": "opaque_password",
            "password": password,
        },
    )

    assert registration.status_code == 201
    assert password not in registration.text
    stored = db_session.scalar(
        select(User).where(User.email == "opaque-password@example.com")
    )
    assert stored is not None
    assert stored.password_hash != password
    assert verify_password_and_update(password, stored.password_hash)[0]

    valid_login = client.post(
        "/api/auth/login",
        json={"identifier": "opaque-password@example.com", "password": password},
    )
    bypass_attempt = client.post(
        "/api/auth/login",
        json={
            "identifier": "opaque-password@example.com",
            "password": "' OR 1=1 --",
        },
    )
    assert valid_login.status_code == 200
    assert bypass_attempt.status_code == 401
    assert password not in caplog.text


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
        {**VALID_REGISTRATION, "password": "short"},
        {**VALID_REGISTRATION, "username": "spaces are invalid"},
        {**VALID_REGISTRATION, "unexpected": True},
    )
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            UserRegister.model_validate(payload)


@pytest.mark.parametrize(
    "password",
    ("sixsix", "a" * 128, "mot de passe", "éàçüñß", "🔑" * 6, "  pad  "),
)
def test_registration_accepts_every_visible_password(password: str) -> None:
    registration = UserRegister.model_validate(
        {**VALID_REGISTRATION, "password": password}
    )

    assert registration.password.get_secret_value() == password


@pytest.mark.parametrize(
    "password",
    ("fives", "🔑" * 5, "a" * 129, "a\tbcdef", "abc\ndef", "abc\x7fdef", "abc\x00def"),
)
def test_registration_rejects_short_long_or_invisible_passwords(password: str) -> None:
    with pytest.raises(ValidationError):
        UserRegister.model_validate({**VALID_REGISTRATION, "password": password})


def test_password_min_length_follows_the_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PASSWORD_MIN_LENGTH", "10")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError):
            UserRegister.model_validate(
                {**VALID_REGISTRATION, "password": "eightchr"}
            )
        assert UserRegister.model_validate(
            {**VALID_REGISTRATION, "password": "tencharact"}
        )
    finally:
        get_settings.cache_clear()


def test_password_max_length_follows_the_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PASSWORD_MAX_LENGTH", "20")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError):
            UserRegister.model_validate({**VALID_REGISTRATION, "password": "a" * 21})
        assert UserRegister.model_validate({**VALID_REGISTRATION, "password": "a" * 20})
        assert UserLogin.model_validate({"identifier": "first_user", "password": "a" * 21})
    finally:
        get_settings.cache_clear()


def test_openapi_documents_the_configured_password_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register = UserRegister.model_json_schema()["properties"]["password"]
    login = UserLogin.model_json_schema()["properties"]["password"]
    assert (register["minLength"], register["maxLength"]) == (6, 128)
    assert login["minLength"] == 1
    assert "maxLength" not in login

    monkeypatch.setenv("PASSWORD_MIN_LENGTH", "10")
    get_settings.cache_clear()
    try:
        assert UserRegister.model_json_schema()["properties"]["password"]["minLength"] == 10
    finally:
        get_settings.cache_clear()


def test_register_route_enforces_the_password_minimum(client: TestClient) -> None:
    too_short = client.post(
        "/api/auth/register",
        json={**VALID_REGISTRATION, "password": "fives"},
    )
    minimum = client.post(
        "/api/auth/register",
        json={**VALID_REGISTRATION, "password": "sixsix"},
    )

    assert too_short.status_code == 422
    assert minimum.status_code == 201


def test_login_accepts_any_stored_password_length() -> None:
    assert UserLogin.model_validate({"identifier": "first_user", "password": "x"})


def test_login_schema_is_strict_and_trims_the_identifier() -> None:
    assert UserLogin.model_validate(
        {"identifier": "  first_user  ", "password": "valid-password"}
    ).identifier == "first_user"

    invalid_payloads = (
        {"email": "first@example.com", "password": "valid-password"},
        {"identifier": "   ", "password": "valid-password"},
        {"identifier": "a" * 255, "password": "valid-password"},
        {"identifier": "first_user", "password": ""},
    )
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            UserLogin.model_validate(payload)


def test_profile_schema_rejects_unsafe_avatars() -> None:
    unsafe_avatars = (
        "/../admin",
        "/avatars/../../private.png",
        "/avatars/%2e%2e/private.png",
        "http://images.example.com/a.png",
        "//images.example.com/a.png",
        "https://user:password@images.example.com/a.png",
        "https://images.example.com:0/a.png",
        "javascript:alert(1)",
        "avatars/relative.png",
        "https://images.example.com/a b.png",
        "https://images.example.com/a\\b.png",
        "https://images.example.com/a\tb.png",
        "  ",
        "/" + "a" * 3000,
    )
    for avatar in unsafe_avatars:
        with pytest.raises(ValidationError):
            UserUpdate.model_validate({"avatar": avatar})


def test_profile_schema_accepts_safe_avatars() -> None:
    safe_avatars = (
        "/static/default-avatar.png",
        "/avatars/nested/user.png",
        "https://images.example.com/a.png",
        "https://images.example.com:8443/a.png",
    )
    for avatar in safe_avatars:
        assert UserUpdate.model_validate({"avatar": avatar}).avatar == avatar


def test_display_name_and_reason_trim_and_reject_control_characters() -> None:
    assert UserUpdate.model_validate(
        {"display_name": "  Jean Dupont  "}
    ).display_name == "Jean Dupont"
    assert UserStatusUpdate.model_validate(
        {"status": "banned", "reason": "  abuse report  "}
    ).reason == "abuse report"

    for blank in ("", "   "):
        with pytest.raises(ValidationError):
            UserUpdate.model_validate({"display_name": blank})
        with pytest.raises(ValidationError):
            UserStatusUpdate.model_validate({"status": "banned", "reason": blank})

    for control in ("a\tb", "a\nb", "a\x7fb"):
        with pytest.raises(ValidationError):
            UserUpdate.model_validate({"display_name": control})
        with pytest.raises(ValidationError):
            UserStatusUpdate.model_validate({"status": "banned", "reason": control})


def test_email_is_normalized_before_validation() -> None:
    registration = UserRegister.model_validate(
        {**VALID_REGISTRATION, "email": "  First.User@Example.COM  "}
    )

    assert str(registration.email) == "first.user@example.com"


def test_cors_allows_configured_frontend_preflight() -> None:
    with TestClient(app, base_url="https://testserver") as test_client:
        response = test_client.options(
            "/api/auth/login",
            headers={
                "Origin": "https://localhost",
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
        api_key_denied = test_client.options(
            "/api/v1/public/projects",
            headers={
                "Origin": "https://localhost",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-api-key",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://localhost"
    )
    assert "authorization" in response.headers[
        "access-control-allow-headers"
    ].lower()
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
    assert api_key_denied.status_code == 400
    assert "x-api-key" not in api_key_denied.headers[
        "access-control-allow-headers"
    ].lower()


def test_registration_never_bootstraps_an_admin(client: TestClient) -> None:
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
    assert first.json()["data"]["user"]["role"] == "user"
    assert second.status_code == 201
    assert second.json()["data"]["user"]["role"] == "user"


def test_concurrent_registration_creates_no_admin(database: object) -> None:
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
    assert admin_count == 0
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


def test_login_failure_is_generic_for_every_unknown_identifier_and_wrong_password(
    client: TestClient,
) -> None:
    assert client.post("/api/auth/register", json=VALID_REGISTRATION).status_code == 201

    failures = [
        client.post(
            "/api/auth/login",
            json={"identifier": identifier, "password": "wrong-password"},
        )
        for identifier in (
            "first@example.com",
            "first_user",
            "unknown@example.com",
            "unknown_user",
        )
    ]

    for failure in failures:
        assert failure.status_code == 401
        assert failure.json() == {
            "success": False,
            "error": "Invalid email, username or password",
        }


def test_unknown_username_still_runs_a_password_verification(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str | None] = []

    def spy(password: str, password_hash: str | None) -> tuple[bool, str | None]:
        calls.append(password_hash)
        return verify_password_and_update(password, password_hash)

    monkeypatch.setattr("app.routers.auth.verify_password_and_update", spy)

    response = client.post(
        "/api/auth/login",
        json={"identifier": "nobody_here", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert calls == [None]


@pytest.mark.parametrize(
    "identifier",
    (
        VALID_REGISTRATION["email"],
        VALID_REGISTRATION["username"],
        "FIRST_USER",
        "  first_user  ",
    ),
)
def test_successful_login_returns_a_usable_token(
    client: TestClient,
    identifier: str,
) -> None:
    registration = client.post("/api/auth/register", json=VALID_REGISTRATION)

    response = client.post(
        "/api/auth/login",
        json={
            "identifier": identifier,
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


def test_login_normalizes_email_identifiers_like_registration(
    client: TestClient,
) -> None:
    registration = client.post(
        "/api/auth/register",
        json={**VALID_REGISTRATION, "email": "first@example.xn--p1ai"},
    )
    assert registration.status_code == 201

    for identifier in ("first@example.xn--p1ai", "FIRST@EXAMPLE.рф"):
        response = client.post(
            "/api/auth/login",
            json={
                "identifier": identifier,
                "password": VALID_REGISTRATION["password"],
            },
        )
        assert response.status_code == 200, identifier


def test_login_rejects_the_legacy_email_field(client: TestClient) -> None:
    assert client.post("/api/auth/register", json=VALID_REGISTRATION).status_code == 201

    response = client.post(
        "/api/auth/login",
        json={
            "email": VALID_REGISTRATION["email"],
            "password": VALID_REGISTRATION["password"],
        },
    )

    assert response.status_code == 422


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
        json={
            "username": "renamed_user",
            "display_name": "Renamed User",
            "avatar": "/avatars/user.png",
        },
    )
    escalation = client.put(
        "/api/users/me",
        headers=headers,
        json={"role": "admin"},
    )

    assert current.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["data"]["user"]["username"] == "renamed_user"
    assert updated.json()["data"]["user"]["display_name"] == "Renamed User"
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


def test_banned_user_cannot_login_or_use_existing_token(
    client: TestClient,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    user = user_factory(
        email="banned@example.com",
        status=UserStatus.BANNED,
    )
    headers = auth_headers(user)

    current = client.get("/api/users/me", headers=headers)
    logins = [
        client.post(
            "/api/auth/login",
            json={"identifier": identifier, "password": "valid-password-42"},
        )
        for identifier in (user.email, user.username)
    ]

    assert current.status_code == 403
    assert current.json()["error"] == "Account is banned"
    for login in logins:
        assert login.status_code == 403
        assert login.json()["error"] == "Account is banned"


def test_registration_matches_a_stored_email_regardless_of_input_case(
    client: TestClient,
) -> None:
    assert client.post("/api/auth/register", json=VALID_REGISTRATION).status_code == 201

    duplicate = client.post(
        "/api/auth/register",
        json={
            **VALID_REGISTRATION,
            "email": "  FIRST@Example.COM ",
            "username": "other_name",
        },
    )
    login = client.post(
        "/api/auth/login",
        json={
            "identifier": " FIRST@EXAMPLE.COM ",
            "password": VALID_REGISTRATION["password"],
        },
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"] == "Email already registered"
    assert login.status_code == 200
    assert login.json()["data"]["user"]["email"] == "first@example.com"


def test_usernames_are_unique_case_insensitively(client: TestClient) -> None:
    first = client.post("/api/auth/register", json=VALID_REGISTRATION)

    shadowed = client.post(
        "/api/auth/register",
        json={
            **VALID_REGISTRATION,
            "email": "second@example.com",
            "username": "First_User",
        },
    )

    assert first.status_code == 201
    assert first.json()["data"]["user"]["username"] == "first_user"
    assert shadowed.status_code == 409
    assert shadowed.json()["error"] == "Username already taken"


def test_profile_rename_preserves_casing_but_cannot_shadow_another_user(
    client: TestClient,
) -> None:
    first = client.post("/api/auth/register", json=VALID_REGISTRATION)
    second = client.post(
        "/api/auth/register",
        json={
            "email": "second@example.com",
            "username": "second_user",
            "password": "valid-password",
        },
    )
    second_headers = {"Authorization": f"Bearer {second.json()['data']['token']}"}

    shadowing = client.put(
        "/api/users/me",
        headers=second_headers,
        json={"username": "First_User"},
    )
    cased = client.put(
        "/api/users/me",
        headers=second_headers,
        json={"username": "Second_User"},
    )

    assert first.status_code == 201
    assert shadowing.status_code == 409
    assert cased.status_code == 200
    assert cased.json()["data"]["user"]["username"] == "Second_User"
