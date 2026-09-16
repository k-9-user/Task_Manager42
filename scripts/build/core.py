from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]
CERTS = ROOT / "nginx/certs"
CERT = CERTS / "localhost.crt"
KEY = CERTS / "localhost.key"
SECRETS = ROOT / "secrets"
COMPOSE = [
    "docker", "compose", "--project-name", "task-manager", "--file",
    str(ROOT / "docker-compose.yml"), "--env-file", str(ROOT / ".env"),
]
ACTIONS = {
    "setup", "check", "up", "down", "clean", "fclean", "re",
    "logs", "ps", "smoke", "test", "reset-db",
}
APP_IMAGES = ("task-manager-back:latest", "task-manager-front:latest")
ENV_NAMES = (
    "POSTGRES_DB", "POSTGRES_USER", "JWT_EXPIRATION", "OAUTH_GOOGLE_CLIENT_ID",
    "OAUTH_GOOGLE_REDIRECT_URI", "CORS_ORIGINS", "UPLOAD_DIR",
    "MAX_UPLOAD_SIZE_MB", "FORWARDED_ALLOW_IPS", "BOOTSTRAP_ADMIN_EMAIL",
    "BOOTSTRAP_ADMIN_USERNAME", "VITE_API_URL",
)
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


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(args, *, quiet=False, env=None):
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=quiet,
        check=False,
    )
    require(result.returncode == 0, f"{args[0]} command failed (exit {result.returncode})")
    return result.stdout if quiet else None


def tools(*names):
    for name in names:
        require(shutil.which(name), f"Missing tool: {name}")
