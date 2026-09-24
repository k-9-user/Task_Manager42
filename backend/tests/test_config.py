from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import (
    BootstrapSettings,
    ConfigurationError,
    DatabaseSettings,
    Settings,
    get_settings,
)


VALID_SECRET = "f" * 40
OTHER_VALID_SECRET = "a1b2c3d4" * 6


def _settings(**overrides: object) -> Settings:
    """Build Settings, filling unset fields from the test environment."""

    return Settings(**overrides)


def test_signing_secrets_reject_env_example_placeholders() -> None:
    placeholders = (
        "replace_with_a_random_32_plus_character_secret",
        "replace_with_a_random_32_plus_character_jwt_secret",
        "replace_with_a_random_32_plus_character_oauth_secret",
    )
    for placeholder in placeholders:
        with pytest.raises(ValidationError):
            _settings(jwt_secret=placeholder)
        with pytest.raises(ValidationError):
            _settings(oauth_session_secret=placeholder)


def test_signing_secrets_reject_short_unprintable_and_non_ascii_values() -> None:
    invalid_secrets = (
        "too-short",
        "f" * 31,
        "f" * 20 + " " + "f" * 20,
        "f" * 20 + "\t" + "f" * 20,
        "f" * 20 + "\n" + "f" * 20,
        "f" * 20 + "\x7f" + "f" * 20,
        "é" * 40,
    )
    for secret in invalid_secrets:
        with pytest.raises(ValidationError):
            _settings(jwt_secret=secret)


def test_jwt_and_oauth_session_secrets_must_differ() -> None:
    with pytest.raises(ValidationError):
        _settings(jwt_secret=VALID_SECRET, oauth_session_secret=VALID_SECRET)

    settings = _settings(
        jwt_secret=VALID_SECRET,
        oauth_session_secret=OTHER_VALID_SECRET,
    )

    assert settings.jwt_secret.get_secret_value() == VALID_SECRET
    assert settings.oauth_session_secret.get_secret_value() == OTHER_VALID_SECRET


def test_google_redirect_uri_must_be_a_plain_https_url() -> None:
    invalid_uris = (
        "http://localhost:8443/api/auth/oauth/google/callback",
        "https://localhost:8443/callback#fragment",
        "https://user:password@localhost/callback",
        "https:///callback",
        "https://localhost:99999/callback",
        "https://localhost/call back",
        "https://localhost/call\\back",
        "https://localhost/call\tback",
        "//localhost/callback",
        "not-a-url",
    )
    for uri in invalid_uris:
        with pytest.raises(ValidationError):
            _settings(oauth_google_redirect_uri=uri)


def test_google_redirect_uri_accepts_https_and_an_unset_value() -> None:
    configured = _settings(
        oauth_google_redirect_uri=(
            "https://localhost/api/auth/oauth/google/callback"
        )
    )
    unset = _settings(oauth_google_redirect_uri="")

    assert configured.oauth_google_redirect_uri.endswith("/callback")
    assert unset.oauth_google_redirect_uri == ""


def test_google_client_id_and_secret_must_be_configured_together() -> None:
    with pytest.raises(ValidationError):
        _settings(
            oauth_google_client_id="local-client",
            oauth_google_client_secret="",
        )
    with pytest.raises(ValidationError):
        _settings(
            oauth_google_client_id="",
            oauth_google_client_secret="local-secret",
        )


def test_database_settings_load_database_url_from_secret_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = "postgresql://user:private-password@db:5432/taskmanager"
    (tmp_path / "database_url").write_text(value)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = DatabaseSettings(_secrets_dir=tmp_path, _env_file=None)

    assert settings.database_url.get_secret_value() == value


def test_bootstrap_settings_validate_identity_and_password() -> None:
    valid = BootstrapSettings(
        database_url="sqlite+pysqlite:///:memory:",
        bootstrap_admin_email="admin@example.com",
        bootstrap_admin_username="admin",
        bootstrap_admin_password="valid-password-42",
    )
    assert str(valid.bootstrap_admin_email) == "admin@example.com"

    for overrides in (
        {"bootstrap_admin_email": "invalid"},
        {"bootstrap_admin_username": "bad user"},
        {"bootstrap_admin_password": "short"},
        {"bootstrap_admin_password": "a" * 129},
    ):
        with pytest.raises(ValidationError):
            BootstrapSettings(**({
                "database_url": "sqlite+pysqlite:///:memory:",
                "bootstrap_admin_email": "admin@example.com",
                "bootstrap_admin_username": "admin",
                "bootstrap_admin_password": "valid-password-42",
            } | overrides))


def test_cached_settings_redact_invalid_secret_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leaked = "short-secret-value"
    monkeypatch.setenv("JWT_SECRET", leaked)
    get_settings.cache_clear()
    try:
        with pytest.raises(ConfigurationError) as error:
            get_settings()
    finally:
        get_settings.cache_clear()

    assert "jwt_secret" in str(error.value)
    assert leaked not in str(error.value)


def test_cached_settings_redact_model_validation_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leaked = "private-google-client-id"
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", leaked)
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(ConfigurationError) as error:
            get_settings()
    finally:
        get_settings.cache_clear()

    assert "oauth_google_client_secret" in str(error.value)
    assert leaked not in str(error.value)


def test_cors_origins_parse_from_a_comma_separated_string() -> None:
    parsed = _settings(cors_origins="https://localhost, https://localhost:5173")
    single = _settings(cors_origins="https://localhost")

    assert parsed.cors_origins == [
        "https://localhost",
        "https://localhost:5173",
    ]
    assert single.cors_origins == ["https://localhost"]


def test_bootstrap_admin_email_is_optional_and_normalized() -> None:
    assert _settings(_env_file=None).bootstrap_admin_email is None
    assert (
        _settings(bootstrap_admin_email="  Admin@Example.COM ").bootstrap_admin_email
        == "admin@example.com"
    )


def test_cors_origins_reject_an_empty_declaration() -> None:
    for value in ("", "   ", ",", " , "):
        with pytest.raises(ValidationError):
            _settings(cors_origins=value)


def test_numeric_settings_must_be_positive() -> None:
    for value in (0, -1):
        with pytest.raises(ValidationError):
            _settings(jwt_expiration=value)
        with pytest.raises(ValidationError):
            _settings(max_upload_size_mb=value)
        with pytest.raises(ValidationError):
            _settings(password_min_length=value)
        with pytest.raises(ValidationError):
            _settings(password_max_length=value)


def test_password_limits_come_from_the_environment_and_stay_ordered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    assert (settings.password_min_length, settings.password_max_length) == (6, 128)
    assert _settings(password_min_length=20, password_max_length=20)
    with pytest.raises(ValidationError):
        _settings(password_min_length=21, password_max_length=20)

    for name in ("PASSWORD_MIN_LENGTH", "PASSWORD_MAX_LENGTH"):
        with monkeypatch.context() as patched:
            patched.delenv(name)
            with pytest.raises(ValidationError):
                Settings()
