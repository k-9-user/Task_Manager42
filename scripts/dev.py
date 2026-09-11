"""Local dev tooling. Stdlib only; .env is data, never executable shell input."""

import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
CERTS = ROOT / "nginx/certs"
CERT = CERTS / "localhost.crt"
KEY = CERTS / "localhost.key"
COMPOSE = ["docker", "compose", "--project-name", "task-manager", "--file",
           str(ROOT / "docker-compose.yml"), "--env-file", str(ROOT / ".env")]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(args, *, quiet=False, env=None):
    result = subprocess.run(args, cwd=ROOT, env=env, text=True,
                            capture_output=quiet, check=False)
    # Captured output can contain credentials; never include it in errors.
    require(result.returncode == 0, f"{args[0]} command failed (exit {result.returncode})")
    return result.stdout if quiet else None


def tools(*names):
    for name in names:
        require(shutil.which(name), f"Missing tool: {name}")


def read_env(path):
    require(path.is_file(), f"Missing {path.name}; run make setup")
    values = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=([^\s\"'`$#\\]*)", line)
        require(match is not None, f"{path.name}:{number}: use plain KEY=value (no expansion or quotes)")
        key, value = match.groups()
        require(key not in values, f"{path.name}:{number}: duplicate key {key}")
        values[key] = value
    return values


def compose_env():
    values = read_env(ROOT / ".env")
    allowed = read_env(ROOT / ".env.example")
    require(values.keys() <= allowed.keys(), ".env contains unsupported keys; use only keys in .env.example")
    # Host variables cannot silently override the checked .env or select another project.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("COMPOSE_") and k not in allowed}
    env.update(values)
    return env


def local_docker_env(env):
    env = env.copy()
    context = env.get("DOCKER_CONTEXT")
    if not context and env.get("DOCKER_HOST"):
        context = "DOCKER_HOST override"
        endpoint = env["DOCKER_HOST"]
    else:
        context = context or run(["docker", "context", "show"], quiet=True, env=env).strip()
        info = json.loads(run(["docker", "context", "inspect", context], quiet=True, env=env))
        endpoint = info[0]["Endpoints"]["docker"]["Host"]
    require(re.fullmatch(r"unix:///[^\s?#]+|npipe:////\./pipe/[^\s/?#]+", endpoint),
            "Local Docker endpoint required: only Unix sockets or local named pipes are allowed; TCP/SSH are refused")
    # Pin the resolved endpoint, not a mutable context name, for every Docker call.
    env.pop("DOCKER_CONTEXT", None)
    env["DOCKER_HOST"] = endpoint
    return env, context


def setup():
    tools("openssl")
    if not (ROOT / ".env").exists():
        template = (ROOT / ".env.example").read_text()
        for placeholder in ("replace_with_generated_database_password",
                            "replace_with_a_random_32_plus_character_jwt_secret",
                            "replace_with_a_random_32_plus_character_oauth_secret"):
            template = template.replace(placeholder, secrets.token_urlsafe(36))
        fd = os.open(ROOT / ".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(template)
        print("Created .env with independent secrets.")
    else:
        print("Preserved existing .env.")
    require(CERT.exists() == KEY.exists(), "Incomplete TLS pair; restore it or remove both files before setup")
    if not CERT.exists():
        CERTS.mkdir(mode=0o700, parents=True, exist_ok=True)
        require(CERTS.stat().st_mode & 0o077 == 0, "nginx/certs must be private (chmod 700 nginx/certs)")
        with tempfile.TemporaryDirectory(dir=CERTS) as temporary:
            cert, key = Path(temporary) / "cert", Path(temporary) / "key"
            run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                 "-days", "365", "-subj", "/CN=localhost", "-addext",
                 "subjectAltName=DNS:localhost,IP:127.0.0.1",
                 "-keyout", str(key), "-out", str(cert)], quiet=True)
            # Individual bind mounts let unprivileged nginx read these files;
            # the 0700 host parent prevents other host users reading the key.
            for source, target in ((cert, CERT), (key, KEY)):
                source.chmod(0o644)
                os.link(source, target)
        print("Created local TLS pair; host trust store unchanged.")
    else:
        print("Preserved existing TLS pair.")


def validate_env(values):
    allowed = read_env(ROOT / ".env.example")
    require(values.keys() == allowed.keys(), ".env must contain exactly the keys in .env.example")
    for name, value in values.items():
        require(not any(word in value.lower() for word in
                        ("replace_with", "changeme", "change_me", "your_secret", "example-secret")),
                f"{name} contains a placeholder")
    secret_names = ("JWT_SECRET", "OAUTH_SESSION_SECRET", "POSTGRES_PASSWORD")
    for name in secret_names:
        require(len(values[name]) >= 32 and re.fullmatch(r"[A-Za-z0-9_-]+", values[name]),
                f"{name} must be at least 32 URL-safe characters")
        require(not values[name].lower().startswith("test"), f"{name} must not use test credentials")
    require(len({values[name] for name in secret_names}) == 3, "JWT, OAuth and database secrets must differ")
    for name in ("POSTGRES_DB", "POSTGRES_USER"):
        require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", values[name]), f"Invalid {name}")
    require(values["POSTGRES_DB"] != "taskmanager_test", "Dev database must not be taskmanager_test")
    expected = (f"postgresql://{values['POSTGRES_USER']}:{values['POSTGRES_PASSWORD']}"
                f"@db:5432/{values['POSTGRES_DB']}")
    require(values["DATABASE_URL"] == expected, "DATABASE_URL must match POSTGRES_* and db:5432 exactly")
    for name in ("CORS_ORIGINS", "VITE_API_URL"):
        require(values[name] == "https://localhost:8443", f"{name} must be https://localhost:8443")
    for name in ("JWT_EXPIRATION", "MAX_UPLOAD_SIZE_MB"):
        require(re.fullmatch(r"[0-9]+", values[name]) and values[name].lstrip("0"),
                f"{name} must be a positive integer")
    require(values["UPLOAD_DIR"] == "/app/uploads", "UPLOAD_DIR must be /app/uploads for persistent storage")
    require(values["OAUTH_GOOGLE_REDIRECT_URI"] == "https://localhost:8443/api/auth/oauth/google/callback",
            "OAUTH_GOOGLE_REDIRECT_URI must be https://localhost:8443/api/auth/oauth/google/callback")
    try:
        for network in values["FORWARDED_ALLOW_IPS"].split(","):
            ipaddress.ip_network(network)
    except ValueError:
        raise ValueError("FORWARDED_ALLOW_IPS must be a comma-separated list of IP addresses or CIDRs") from None
    enabled = bool(values["OAUTH_GOOGLE_CLIENT_ID"])
    require(enabled == bool(values["OAUTH_GOOGLE_CLIENT_SECRET"]),
            "Set both OAUTH_GOOGLE_CLIENT_ID and OAUTH_GOOGLE_CLIENT_SECRET, or leave both empty")
    if not enabled:
        print("Warning: Google OAuth is disabled; both Google credentials are empty.", file=sys.stderr)


def check():
    validate_env(read_env(ROOT / ".env"))
    tools("docker", "openssl", "curl")
    env, context = local_docker_env(compose_env())
    run(["docker", "compose", "version"], quiet=True, env=env)
    run(["docker", "info"], quiet=True, env=env)
    require(CERT.is_file() and KEY.is_file() and os.access(CERT, os.R_OK)
            and os.access(KEY, os.R_OK), "Missing or unreadable TLS pair; run make setup")
    require(CERTS.stat().st_mode & 0o077 == 0, "nginx/certs must be private (chmod 700 nginx/certs)")
    require(all(path.stat().st_mode & 0o004 for path in (CERT, KEY)),
            "TLS files need read permission for unprivileged nginx inside private nginx/certs")
    run(["openssl", "x509", "-in", str(CERT), "-checkend", "0", "-noout"], quiet=True)
    san = run(["openssl", "x509", "-in", str(CERT), "-noout", "-ext", "subjectAltName"], quiet=True)
    names = {name.strip() for name in san.splitlines()[-1].split(",")}
    require({"DNS:localhost", "IP Address:127.0.0.1"} <= names, "TLS SAN must include localhost and 127.0.0.1")
    public = run(["openssl", "x509", "-in", str(CERT), "-pubkey", "-noout"], quiet=True)
    private_public = run(["openssl", "pkey", "-in", str(KEY), "-passin", "pass:", "-pubout"], quiet=True)
    require(public == private_public, "TLS certificate and key do not match")
    run(["openssl", "verify", "-CAfile", str(CERT), str(CERT)], quiet=True)
    run(COMPOSE + ["--profile", "test", "config", "--quiet"], quiet=True, env=env)
    print("Checks passed: tools, daemon, env, TLS and Compose (no secrets printed).")
    return env, context


def smoke():
    def get(path):
        return run(["curl", "--fail", "--silent", "--show-error", "--noproxy", "*",
                    "--connect-timeout", "5", "--max-time", "15", "--cacert", str(CERT),
                    "https://localhost:8443" + path], quiet=True)
    require(json.loads(get("/health")) == {"status": "ok", "db": "ok"}, "Health check failed")
    root = get("/")
    require('<div id="root">' in root and 'src="/src/main.jsx"' in root, "Frontend root or source entry is missing")
    entry = get("/src/main.jsx")
    require("/node_modules/.vite/deps/" in entry and "/src/App.jsx" in entry
            and "createRoot" in entry and "<StrictMode>" not in entry,
            "Frontend entry is not Vite-transformed JavaScript")
    locale = json.loads(get("/locales/en/translation.json"))
    require(isinstance(locale, dict) and isinstance(locale.get("navbar"), dict)
            and bool(locale["navbar"].get("projects")), "Frontend English locale is missing")
    paths = json.loads(get("/openapi.json"))["paths"]
    expected = {"/health": "get", "/api/auth/login": "post", "/api/auth/register": "post",
                "/api/projects": "get", "/api/tasks/{task_id}": "put",
                "/api/notifications": "get", "/api/search/tasks": "get", "/api/gdpr/export": "get",
                "/api/users/me": "get", "/api/v1/public/tasks": "get",
                "/api/export": "get", "/api/import": "post",
                "/api/tasks/{task_id}/attachments": "post", "/api/attachments/{attachment_id}": "delete"}
    require(all(method in paths.get(path, {}) for path, method in expected.items()),
            "Expected OpenAPI routes are missing")
    print("Smoke passed: trusted local TLS, database health, frontend entry/locale and all API families; no user mutations.")


def main():
    action = sys.argv[1]
    if action == "setup":
        setup()
        return
    if action in {"check", "up", "test", "smoke", "reset-db"}:
        env, context = check()
    else:
        env, context = local_docker_env(compose_env())
    if action == "up":
        run(COMPOSE + ["up", "--build", "--detach", "--wait"], env=env)
    elif action in {"down", "logs", "ps"}:
        args = {"down": ["--profile", "test", "down"], "logs": ["logs", "--follow", "--tail", "100"], "ps": ["--profile", "test", "ps"]}
        run(COMPOSE + args[action], env=env)
    elif action == "smoke":
        smoke()
    elif action == "test":
        run(COMPOSE + ["--profile", "test", "build", "test"], env=env)
        try:
            run(COMPOSE + ["--profile", "test", "run", "--rm", "test", "python", "-m", "pytest", "-q"]
                + shlex.split(os.environ.get("TESTS", "")), env=env)
        finally:
            run(COMPOSE + ["--profile", "test", "rm", "--stop", "--force", "test-db"], env=env)
    elif action == "reset-db":
        config = json.loads(run(COMPOSE + ["config", "--format", "json"], quiet=True, env=env))
        volume = config["volumes"]["postgres_data"]["name"]
        info = json.loads(run(["docker", "volume", "inspect", volume], quiet=True, env=env))[0]
        labels = info.get("Labels") or {}
        require(labels.get("com.docker.compose.project") == "task-manager"
                and labels.get("com.docker.compose.volume") == "postgres_data",
                "Refusing to remove a volume without matching project/database labels")
        require(input(f"Docker context: {context!r}\nEndpoint: {env['DOCKER_HOST']!r}\n"
                      f"Delete ONLY volume {volume!r}? Type reset-db: ") == "reset-db", "Reset cancelled")
        run(COMPOSE + ["stop", "nginx", "backend", "migrate", "db"], env=env)
        run(COMPOSE + ["rm", "--force", "db"], env=env)
        run(["docker", "volume", "rm", volume], env=env)
        print("Dev database removed; uploads preserved. Run make up to recreate and migrate.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, EOFError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
