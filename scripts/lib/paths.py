"""Repository paths shared by every command."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CERTS = ROOT / "nginx/certs"
CERT = CERTS / "localhost.crt"
KEY = CERTS / "localhost.key"
SECRETS = ROOT / "secrets"
DATA = ROOT / "data"
DATA_VOLUMES = {"postgres_data": "postgres", "backend_uploads": "uploads"}
DATA_DIRS = tuple(DATA_VOLUMES.values())
DATA_BACKUPS = "backups"
