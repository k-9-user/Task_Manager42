import logging
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import anyio
import httpx
import pytest
from authlib.integrations.base_client.errors import OAuthError
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.auth.oauth import get_google_oauth_client
from app.database import SessionLocal
from app.main import app
from app.models.user import User, UserRole
from app.routers.auth import get_google_client


VALID_CLAIMS = {
    "sub": "google-subject-42",
    "email": "google.user@example.com",
    "email_verified": True,
    "picture": "https://images.example.com/avatar.png",
}


class CallbackClient:
    def __init__(self, result: object = None, error: Exception | None = None):
        self.result = result
        self.error = error

    async def authorize_access_token(
        self,
        _request: object,
        **_kwargs: object,
    ) -> object:
        if self.error is not None:
            raise self.error
        return self.result


def _override_google_client(fake_client: object) -> None:
    app.dependency_overrides[get_google_client] = lambda: fake_client


def test_google_client_is_cached_and_uses_pkce() -> None:
    get_google_oauth_client.cache_clear()

    first = get_google_oauth_client()
    second = get_google_oauth_client()
    first.server_metadata.update(
        {
            "authorization_endpoint": "https://accounts.google.com/o/oauth2/auth",
            "_loaded_at": 0,
        }
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "path": "/api/auth/oauth/google",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 443),
            "client": ("127.0.0.1", 1),
            "session": {},
        }
    )

    async def start_oauth() -> RedirectResponse:
        return await first.authorize_redirect(
            request,
            "https://testserver/api/auth/oauth/google/callback",
        )

    response = anyio.run(start_oauth)
    parameters = parse_qs(urlsplit(response.headers["location"]).query)
    state = parameters["state"][0]
    stored_state = request.session[f"_state_google_{state}"]["data"]

    assert first is second
    assert first.client_kwargs["code_challenge_method"] == "S256"
    assert parameters["nonce"][0] == stored_state["nonce"]
    assert parameters["code_challenge_method"] == ["S256"]
    assert stored_state["code_verifier"]
    assert logging.getLogger("authlib.integrations.base_client.sync_app").level == (
        logging.WARNING
    )


def test_google_start_returns_503_when_configuration_is_unavailable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*_args: object) -> object:
        raise RuntimeError("Google OAuth is not configured")

    monkeypatch.setattr("app.routers.auth.get_google_oauth_client", unavailable)

    response = client.get("/api/auth/oauth/google", follow_redirects=False)

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "error": "Google OAuth unavailable",
    }


def test_google_start_delegates_state_nonce_and_pkce_to_authlib(
    client: TestClient,
) -> None:
    captured: dict[str, Any] = {}

    class RedirectClient:
        async def authorize_redirect(
            self,
            request: object,
            redirect_uri: str,
            **kwargs: object,
        ) -> RedirectResponse:
            captured.update(
                request=request,
                redirect_uri=redirect_uri,
                kwargs=kwargs,
            )
            return RedirectResponse("https://accounts.google.com/o/oauth2/auth")

    _override_google_client(RedirectClient())
    response = client.get("/api/auth/oauth/google", follow_redirects=False)

    assert response.status_code in {302, 307}
    assert captured["redirect_uri"].endswith("/api/auth/oauth/google/callback")
    assert captured["kwargs"] == {}


def test_google_callback_rejects_invalid_oauth_protocol(
    client: TestClient,
) -> None:
    protocol_errors = (
        OAuthError(error="missing_state"),
        OAuthError(error="mismatching_state"),
        OAuthError(error="invalid_grant"),
    )
    for error in protocol_errors:
        _override_google_client(CallbackClient(error=error))
        response = client.get("/api/auth/oauth/google/callback")

        assert response.status_code == 400
        assert response.json()["error"] == "Google OAuth failed"


def test_google_callback_creates_then_reuses_a_provider_subject(
    client: TestClient,
) -> None:
    _override_google_client(CallbackClient(result={"userinfo": VALID_CLAIMS}))

    response = client.get("/api/auth/oauth/google/callback")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["token"]
    assert response.json()["data"]["user"]["role"] == "admin"
    with SessionLocal() as session:
        user = session.get(
            User,
            UUID(response.json()["data"]["user"]["id"]),
        )
        assert user is not None
        assert user.oauth_provider == "google"
        assert user.oauth_id == VALID_CLAIMS["sub"]
        assert user.password_hash is None

    changed_claims = {
        **VALID_CLAIMS,
        "email": "provider-renamed@example.com",
    }
    _override_google_client(CallbackClient(result={"userinfo": changed_claims}))

    response = client.get("/api/auth/oauth/google/callback")

    assert response.status_code == 200
    assert response.json()["data"]["user"]["id"] == str(user.id)


def test_google_callback_rejects_invalid_claims(client: TestClient) -> None:
    invalid_claims = (
        {**VALID_CLAIMS, "email_verified": False},
        {**VALID_CLAIMS, "picture": "http://images.example.com/avatar.png"},
    )
    for claims in invalid_claims:
        _override_google_client(CallbackClient(result={"userinfo": claims}))
        response = client.get("/api/auth/oauth/google/callback")

        assert response.status_code == 400


def test_google_callback_maps_provider_transport_failure(
    client: TestClient,
) -> None:
    error = httpx.ConnectError(
        "provider down",
        request=httpx.Request("POST", "https://accounts.google.com/token"),
    )
    _override_google_client(CallbackClient(error=error))

    response = client.get("/api/auth/oauth/google/callback")

    assert response.status_code == 502


def test_google_callback_never_auto_links_a_local_email(
    client: TestClient,
    user_factory: Any,
) -> None:
    user_factory(email=VALID_CLAIMS["email"])
    _override_google_client(CallbackClient(result={"userinfo": VALID_CLAIMS}))

    response = client.get("/api/auth/oauth/google/callback")

    assert response.status_code == 409
    assert response.json()["error"] == "An account with this email already exists"


def test_oauth_only_account_rejects_password_login(
    client: TestClient,
    user_factory: Any,
) -> None:
    user_factory(email="oauth-only@example.com", oauth_id="oauth-only-subject")

    response = client.post(
        "/api/auth/login",
        json={"email": "oauth-only@example.com", "password": "any-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "Invalid email or password"


def test_oauth_failures_do_not_log_secrets(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "oauth-code-token-pkce-secret-42"
    _override_google_client(
        CallbackClient(
            error=OAuthError(error="invalid_request", description=secret)
        )
    )
    caplog.set_level(logging.WARNING, logger="app.routers.auth")

    response = client.get(
        f"/api/auth/oauth/google/callback?code={secret}&state={secret}"
    )

    assert response.status_code == 400
    assert secret not in caplog.text
    assert "category=protocol_or_claims" in caplog.text
