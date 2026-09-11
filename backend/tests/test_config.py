import pytest
from pydantic import ValidationError

from app.config import Settings


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
            "https://localhost:8443/api/auth/oauth/google/callback"
        )
    )
    unset = _settings(oauth_google_redirect_uri="")

    assert configured.oauth_google_redirect_uri.endswith("/callback")
    assert unset.oauth_google_redirect_uri == ""


def test_cors_origins_parse_from_a_comma_separated_string() -> None:
    parsed = _settings(cors_origins="https://localhost:8443, https://localhost:5173")
    single = _settings(cors_origins="https://localhost:8443")

    assert parsed.cors_origins == [
        "https://localhost:8443",
        "https://localhost:5173",
    ]
    assert single.cors_origins == ["https://localhost:8443"]


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
