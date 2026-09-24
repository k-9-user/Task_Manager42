"""Shared test data and throwaway data directories."""

import base64
import contextlib
import hashlib
from pathlib import Path
import tempfile
from unittest.mock import patch

from scripts.lib import data as data_dirs
from scripts.lib import paths


def valid_env():
    return {
        "POSTGRES_DB": "taskmanager",
        "POSTGRES_USER": "user",
        "JWT_EXPIRATION": "3600",
        "OAUTH_GOOGLE_CLIENT_ID": "",
        "OAUTH_GOOGLE_REDIRECT_URI": "https://localhost/api/auth/oauth/google/callback",
        "CORS_ORIGINS": "https://localhost",
        "UPLOAD_DIR": "/app/uploads",
        "MAX_UPLOAD_SIZE_MB": "10",
        "PASSWORD_MIN_LENGTH": "6",
        "PASSWORD_MAX_LENGTH": "128",
        "FORWARDED_ALLOW_IPS": "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
        "BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
        "BOOTSTRAP_ADMIN_USERNAME": "admin",
        "BACKUP_INTERVAL_MINUTES": "60",
        "BACKUP_RETENTION": "24",
        "VITE_API_URL": "https://localhost",
    }


def valid_secrets():
    password = "p" * 40
    return {
        "postgres_password": password,
        "database_url": f"postgresql://user:{password}@db:5432/taskmanager",
        "jwt_secret": "j" * 40,
        "oauth_session_secret": "o" * 40,
        "oauth_google_client_secret": "",
        "bootstrap_admin_password": "a" * 40,
    }


def nonced_page(nonce, *, stamped=None, placeholder=False, preamble=True):
    """A frontend response as nginx returns it once sub_filter has run."""

    stamped = nonce if stamped is None else stamped
    headers = (
        "HTTP/2 200\r\n"
        "content-type: text/html\r\n"
        "content-security-policy: default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'\r\n"
    )
    preamble_tag = f'<script type="module" nonce="{stamped}">injectIntoGlobalHook</script>' if preamble else '<script type="module">injectIntoGlobalHook</script>'
    body = (
        "<!doctype html>"
        + ("VITE_CSP_NONCE" if placeholder else "")
        + preamble_tag
        + '<div id="root"></div>'
        + f'<script src="/src/main.jsx" nonce="{stamped}"></script>'
    )
    return headers + "\r\n" + body


ROOT_PAGE = '<div id="root"></div><script src="/src/main.jsx"></script>'

SWAGGER_BUNDLE = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"
SWAGGER_BOOTSTRAP = "\n    const ui = SwaggerUIBundle({url: '/openapi.json'})\n    "


def docs_page(*, sources=None, bundle=SWAGGER_BUNDLE):
    """/docs as nginx returns it: the Swagger bundle, FastAPI's inline bootstrap and the docs CSP."""

    if sources is None:
        digest = base64.b64encode(hashlib.sha256(SWAGGER_BOOTSTRAP.encode()).digest()).decode()
        sources = f"'self' https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/ 'sha256-{digest}'"
    headers = (
        "HTTP/2 200\r\n"
        "content-type: text/html; charset=utf-8\r\n"
        f"content-security-policy: default-src 'self'; script-src {sources}; style-src 'self' 'unsafe-inline'\r\n"
    )
    body = f'<div id="swagger-ui"></div><script src="{bundle}"></script><script>{SWAGGER_BOOTSTRAP}</script>'
    return headers + "\r\n" + body


@contextlib.contextmanager
def bound_data(populate=True):
    """Point lib/data.py at a throwaway data directory.

    lib/data.py resolves every data path from its own DATA, so one patch covers all commands.
    """

    with tempfile.TemporaryDirectory() as temporary:
        data = Path(temporary).resolve()
        for name in paths.DATA_DIRS:
            directory = data / name
            directory.mkdir()
            if populate:
                (directory / "payload").write_text("state")
                (directory / "nested").mkdir()
                (directory / "nested" / "deep").write_text("state")
        with patch.object(data_dirs, "DATA", data):
            yield data


def compose_volumes(data, *, device_override=None):
    """Compose config payload matching a bound data directory."""

    volumes = {
        logical: {
            "name": f"task-manager_{logical}",
            "driver_opts": {"type": "none", "o": "bind",
                            "device": device_override or str(data / subdirectory)},
        }
        for logical, subdirectory in paths.DATA_VOLUMES.items()
    }
    volumes["frontend_node_modules"] = {"name": "task-manager_frontend_node_modules"}
    return volumes


@contextlib.contextmanager
def backups(*names):
    with bound_data(populate=False) as data:
        directory = data / paths.DATA_BACKUPS
        directory.mkdir()
        for name in names:
            (directory / name).mkdir()
            for part in ("database.sql.gz", "uploads.tar.gz"):
                (directory / name / part).write_text("archive")
        yield data
