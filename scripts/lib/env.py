"""The non-secret .env contract: keys, parser and atomic writer."""

import os
import re
import tempfile

from .process import require


ENV_NAMES = (
    "POSTGRES_DB", "POSTGRES_USER", "JWT_EXPIRATION", "OAUTH_GOOGLE_CLIENT_ID",
    "OAUTH_GOOGLE_REDIRECT_URI", "CORS_ORIGINS", "UPLOAD_DIR",
    "MAX_UPLOAD_SIZE_MB", "FORWARDED_ALLOW_IPS", "BOOTSTRAP_ADMIN_EMAIL",
    "BOOTSTRAP_ADMIN_USERNAME", "BACKUP_INTERVAL_MINUTES", "BACKUP_RETENTION",
    "VITE_API_URL",
)
ADDED_ENV_NAMES = ("BACKUP_INTERVAL_MINUTES", "BACKUP_RETENTION")
LOCAL_URLS = {
    "OAUTH_GOOGLE_REDIRECT_URI": "https://localhost/api/auth/oauth/google/callback",
    "CORS_ORIGINS": "https://localhost",
    "VITE_API_URL": "https://localhost",
}
LEGACY_LOCAL_URLS = {
    "OAUTH_GOOGLE_REDIRECT_URI": "https://localhost:8443/api/auth/oauth/google/callback",
    "CORS_ORIGINS": "https://localhost:8443",
    "VITE_API_URL": "https://localhost:8443",
}


def read_env(path):
    require(path.is_file(), f"Missing {path.name}; run make setup")
    values = {}
    try:
        contents = path.read_text()
    except (OSError, UnicodeError):
        raise ValueError(f"Unable to read {path.name}") from None
    for number, line in enumerate(contents.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=([^\s\"'`$#\\]*)", line)
        require(match is not None, f"{path.name}:{number}: use plain KEY=value (no expansion or quotes)")
        key, value = match.groups()
        require(key not in values, f"{path.name}:{number}: duplicate key {key}")
        values[key] = value
    return values


def write_env(path, template, values):
    rendered = []
    for line in template.splitlines():
        match = re.match(r"([A-Z][A-Z0-9_]*)=", line)
        rendered.append(f"{match.group(1)}={values[match.group(1)]}" if match else line)
    fd, temporary = tempfile.mkstemp(prefix=".env.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write("\n".join(rendered) + "\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
