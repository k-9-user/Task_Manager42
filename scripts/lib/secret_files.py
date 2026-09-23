"""File-backed Docker secrets: names, reader, writer and generator."""

import os
import secrets
import stat

from .paths import SECRETS
from .process import require


SECRET_NAMES = (
    "postgres_password", "database_url", "jwt_secret", "oauth_session_secret",
    "oauth_google_client_secret", "bootstrap_admin_password",
)
LEGACY_SECRET_NAMES = {
    "POSTGRES_PASSWORD": "postgres_password",
    "DATABASE_URL": "database_url",
    "JWT_SECRET": "jwt_secret",
    "OAUTH_SESSION_SECRET": "oauth_session_secret",
    "OAUTH_GOOGLE_CLIENT_SECRET": "oauth_google_client_secret",
}
SECRET_ENV_NAMES = set(LEGACY_SECRET_NAMES) | {"BOOTSTRAP_ADMIN_PASSWORD"}
SECRET_METADATA = {"README.md"}


def payload_entries(secret_dir):
    if not secret_dir.exists():
        return []
    require(secret_dir.is_dir() and not secret_dir.is_symlink(), f"{secret_dir.name} must be a real directory")
    return [entry for entry in secret_dir.iterdir() if entry.name not in SECRET_METADATA]


def read_secret(path):
    require(not path.is_symlink(), f"Secret file {path.name} must not be a symlink")
    try:
        mode = path.lstat().st_mode
    except OSError:
        raise ValueError(f"Secret file {path.name} is unreadable") from None
    require(stat.S_ISREG(mode), f"Secret file {path.name} must be a regular file")
    require(mode & 0o022 == 0, f"Secret file {path.name} must not be group/world writable")
    require(mode & 0o004, f"Secret file {path.name} must be container-readable")
    try:
        value = path.read_text()
    except (OSError, UnicodeError):
        raise ValueError(f"Secret file {path.name} is unreadable") from None
    require("\n" not in value and "\r" not in value, f"Secret file {path.name} must contain exactly one value without a newline")
    return value


def read_secret_files(secret_dir=SECRETS):
    require(secret_dir.is_dir() and not secret_dir.is_symlink(), f"Missing {secret_dir.name} directory; run make setup")
    require(secret_dir.stat().st_mode & 0o077 == 0, f"{secret_dir.name} directory must be private (chmod 700 {secret_dir.name})")
    entries = payload_entries(secret_dir)
    names = {entry.name for entry in entries}
    for entry in entries:
        require(not entry.is_symlink(), f"Secret file {entry.name} must not be a symlink")
    unexpected = names - set(SECRET_NAMES)
    missing = set(SECRET_NAMES) - names
    require(not unexpected, f"{secret_dir.name} contains unexpected secret files")
    require(not missing, f"{secret_dir.name} is missing required secret files")
    return {name: read_secret(secret_dir / name) for name in SECRET_NAMES}


def write_secret(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w") as output:
        output.write(value)
    path.chmod(0o644)


def generate_secrets(env_values):
    postgres_password = secrets.token_urlsafe(36)
    return {
        "postgres_password": postgres_password,
        "database_url": (
            f"postgresql://{env_values['POSTGRES_USER']}:{postgres_password}"
            f"@db:5432/{env_values['POSTGRES_DB']}"
        ),
        "jwt_secret": secrets.token_urlsafe(36),
        "oauth_session_secret": secrets.token_urlsafe(36),
        "oauth_google_client_secret": "",
        "bootstrap_admin_password": secrets.token_urlsafe(36),
    }
