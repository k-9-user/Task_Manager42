"""Shared test data and throwaway data directories."""

import contextlib
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
