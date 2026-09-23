"""Validation of .env values together with the secret files."""

import ipaddress
import re
import sys

from .env import ENV_NAMES
from .process import require
from .secret_files import SECRET_NAMES, read_secret_files


def _contains_placeholder(value):
    return any(word in value.lower() for word in
               ("replace_with", "changeme", "change_me", "your_secret", "example-secret"))


def validate_config(values, secret_values):
    require(set(values) == set(ENV_NAMES),
            ".env must contain exactly the documented non-secret keys; run make setup to add new keys")
    require(set(secret_values) == set(SECRET_NAMES),
            "secrets directory must contain exactly the documented secret files")
    for name, value in values.items():
        require(not _contains_placeholder(value), f"{name} contains a placeholder")
    for name, value in secret_values.items():
        require(not _contains_placeholder(value), f"Secret file {name} contains a placeholder")

    for name in ("postgres_password", "jwt_secret", "oauth_session_secret"):
        value = secret_values[name]
        require(len(value) >= 32 and re.fullmatch(r"[A-Za-z0-9_-]+", value),
                f"Secret file {name} must be at least 32 URL-safe characters")
        require(not value.lower().startswith("test"),
                f"Secret file {name} must not use test credentials")
    admin_password = secret_values["bootstrap_admin_password"]
    require(12 <= len(admin_password) <= 128
            and not any(ord(character) < 0x20 or ord(character) == 0x7f
                        for character in admin_password),
            "Secret file bootstrap_admin_password must be 12-128 printable characters")
    independent = [secret_values[name] for name in
                   ("postgres_password", "jwt_secret", "oauth_session_secret",
                    "bootstrap_admin_password")]
    require(len(set(independent)) == len(independent),
            "Database, signing and bootstrap-admin secrets must differ")

    for name in ("POSTGRES_DB", "POSTGRES_USER"):
        require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", values[name]), f"Invalid {name}")
    require(values["POSTGRES_DB"] != "taskmanager_test", "Dev database must not be taskmanager_test")
    expected = (f"postgresql://{values['POSTGRES_USER']}:{secret_values['postgres_password']}"f"@db:5432/{values['POSTGRES_DB']}")
    require(secret_values["database_url"] == expected, "Secret file database_url must match POSTGRES_* and postgres_password")

    for name in ("CORS_ORIGINS", "VITE_API_URL"):
        require(values[name] == "https://localhost", f"{name} must be https://localhost")

    for name in ("JWT_EXPIRATION", "MAX_UPLOAD_SIZE_MB", "BACKUP_INTERVAL_MINUTES", "BACKUP_RETENTION"):
        require(re.fullmatch(r"[0-9]+", values[name]) and values[name].lstrip("0"), f"{name} must be a positive integer")
    require(values["UPLOAD_DIR"] == "/app/uploads", "UPLOAD_DIR must be /app/uploads for persistent storage")
    require(values["OAUTH_GOOGLE_REDIRECT_URI"] == "https://localhost/api/auth/oauth/google/callback", "OAUTH_GOOGLE_REDIRECT_URI must be https://localhost/api/auth/oauth/google/callback")
    try:
        for network in values["FORWARDED_ALLOW_IPS"].split(","):
            ipaddress.ip_network(network)
    except ValueError:
        raise ValueError("FORWARDED_ALLOW_IPS must be a comma-separated list of IP addresses or CIDRs") from None

    require(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", values["BOOTSTRAP_ADMIN_EMAIL"]),
            "BOOTSTRAP_ADMIN_EMAIL must be a valid email address")
    require(re.fullmatch(r"[A-Za-z0-9._-]{3,50}", values["BOOTSTRAP_ADMIN_USERNAME"]),
            "BOOTSTRAP_ADMIN_USERNAME must be 3-50 safe characters")
    google_secret = secret_values["oauth_google_client_secret"]
    require(not any(ord(character) < 0x20 or ord(character) == 0x7f
                    for character in google_secret),
            "Secret file oauth_google_client_secret must contain printable characters")
    enabled = bool(values["OAUTH_GOOGLE_CLIENT_ID"])
    require(enabled == bool(google_secret),
            "Set both OAUTH_GOOGLE_CLIENT_ID and oauth_google_client_secret, or leave both empty")
    if not enabled:
        print("Warning: Google OAuth is disabled; both Google credentials are empty.", file=sys.stderr)


def validate_env(values):
    """Compatibility entry point used by older callers and tests."""

    validate_config(values, read_secret_files())
