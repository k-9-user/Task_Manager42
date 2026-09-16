"""Local dev tooling. Stdlib only; .env is data, never executable shell input."""

import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
CERTS = ROOT / "nginx/certs"
CERT = CERTS / "localhost.crt"
KEY = CERTS / "localhost.key"
SECRETS = ROOT / "secrets"
COMPOSE = ["docker", "compose", "--project-name", "task-manager", "--file",
           str(ROOT / "docker-compose.yml"), "--env-file", str(ROOT / ".env")]
ACTIONS = {"setup", "check", "up", "down", "clean", "fclean", "re",
           "logs", "ps", "smoke", "test", "reset-db"}
APP_IMAGES = ("task-manager-backend:development", "task-manager-frontend:latest")
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


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(args, *, quiet=False, env=None):
    result = subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=quiet, check=False)
    require(result.returncode == 0, f"{args[0]} command failed (exit {result.returncode})")
    return result.stdout if quiet else None


def tools(*names):
    for name in names:
        require(shutil.which(name), f"Missing tool: {name}")


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


def _payload_entries(secret_dir):
    if not secret_dir.exists():
        return []
    require(secret_dir.is_dir() and not secret_dir.is_symlink(), f"{secret_dir.name} must be a real directory")
    return [entry for entry in secret_dir.iterdir() if entry.name not in SECRET_METADATA]


def _read_secret(path):
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
    entries = _payload_entries(secret_dir)
    names = {entry.name for entry in entries}
    for entry in entries:
        require(not entry.is_symlink(), f"Secret file {entry.name} must not be a symlink")
    unexpected = names - set(SECRET_NAMES)
    missing = set(SECRET_NAMES) - names
    require(not unexpected, f"{secret_dir.name} contains unexpected secret files")
    require(not missing, f"{secret_dir.name} is missing required secret files")
    return {name: _read_secret(secret_dir / name) for name in SECRET_NAMES}


def _write_secret(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w") as output:
        output.write(value)
    path.chmod(0o644)


def _write_env(path, template, values):
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


def _generated_secrets(env_values):
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


def _contains_placeholder(value):
    return any(word in value.lower() for word in
               ("replace_with", "changeme", "change_me", "your_secret", "example-secret"))


def validate_config(values, secret_values):
    require(set(values) == set(ENV_NAMES), ".env must contain exactly the documented non-secret keys")
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
    expected = (f"postgresql://{values['POSTGRES_USER']}:{secret_values['postgres_password']}"
                f"@db:5432/{values['POSTGRES_DB']}")
    require(secret_values["database_url"] == expected,
            "Secret file database_url must match POSTGRES_* and postgres_password")
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


def setup_configuration(root=ROOT):
    env_example = root / ".env.example"
    env_path = root / ".env"
    secret_dir = root / "secrets"
    template = env_example.read_text()
    example_values = read_env(env_example)
    require(set(example_values) == set(ENV_NAMES),
            ".env.example does not match the supported configuration keys")

    secret_dir.mkdir(mode=0o700, exist_ok=True)
    secret_dir.chmod(0o700)
    payload_entries = _payload_entries(secret_dir)

    if not env_path.exists():
        require(not payload_entries, "Secret files exist without .env; restore matching configuration")
        env_values = example_values
        secret_values = _generated_secrets(env_values)
        validate_config(env_values, secret_values)
        for name, value in secret_values.items():
            _write_secret(secret_dir / name, value)
        _write_env(env_path, template, env_values)
        print("Created .env and private file-backed secrets.")
        return

    current = read_env(env_path)
    legacy_keys = set(current) & set(LEGACY_SECRET_NAMES)
    if not legacy_keys:
        require(set(current) == set(ENV_NAMES),
                ".env must contain exactly the documented non-secret keys")
        validate_config(current, read_secret_files(secret_dir))
        print("Preserved existing .env and secret files.")
        return

    expected_legacy = (set(ENV_NAMES) - {"BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_USERNAME"}) \
        | set(LEGACY_SECRET_NAMES)
    require(set(current) == expected_legacy,
            "Legacy .env must be complete before secret migration")
    env_values = {
        name: current.get(name, example_values[name])
        for name in ENV_NAMES
    }
    secret_values = {
        new_name: current[old_name]
        for old_name, new_name in LEGACY_SECRET_NAMES.items()
    }
    existing = {entry.name: entry for entry in payload_entries}
    unexpected = set(existing) - set(SECRET_NAMES)
    require(not unexpected, "secrets contains unexpected secret files")
    admin_path = secret_dir / "bootstrap_admin_password"
    if admin_path.exists():
        secret_values["bootstrap_admin_password"] = _read_secret(admin_path)
    else:
        secret_values["bootstrap_admin_password"] = secrets.token_urlsafe(36)
    validate_config(env_values, secret_values)
    for name, value in secret_values.items():
        path = secret_dir / name
        if path.exists():
            require(_read_secret(path) == value,
                    f"Secret file {name} conflicts with legacy .env; nothing was overwritten")
        else:
            _write_secret(path, value)
    _write_env(env_path, template, env_values)
    print("Migrated legacy .env secrets into private files.")


def compose_env():
    values = read_env(ROOT / ".env")
    allowed = read_env(ROOT / ".env.example")
    require(values.keys() <= allowed.keys(), ".env contains unsupported keys; use only keys in .env.example")
    # Host variables cannot silently override the checked .env or select another project.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("COMPOSE_") and k not in allowed and k not in SECRET_ENV_NAMES}
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
    setup_configuration()
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


def validate_certificate_sans(output):
    names = {
        name.strip()
        for line in output.splitlines()
        for name in line.split(",")
    }
    require(
        {"DNS:localhost", "IP Address:127.0.0.1"} <= names,
        "TLS certificate SAN must include localhost and 127.0.0.1; "
        "remove both local TLS files and run make setup to regenerate them",
    )


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
    validate_certificate_sans(san)
    public = run(["openssl", "x509", "-in", str(CERT), "-pubkey", "-noout"], quiet=True)
    private_public = run(["openssl", "pkey", "-in", str(KEY), "-passin", "pass:", "-pubout"], quiet=True)
    require(public == private_public, "TLS certificate and key do not match")
    run(["openssl", "verify", "-CAfile", str(CERT), str(CERT)], quiet=True)
    run(COMPOSE + ["--profile", "test", "config", "--quiet"], quiet=True, env=env)
    print("Checks passed: tools, daemon, env, secrets, TLS and Compose (no secrets printed).")
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
                 "/api/tasks/{task_id}/attachments": "post", "/api/attachments/{attachment_id}": "delete",
                 "/api/auth/oauth/google/exchange": "post", "/api/api-keys": "post",
                 "/api/api-keys/{key_id}/rotate": "post"}
    require(all(method in paths.get(path, {}) for path, method in expected.items()),
            "Expected OpenAPI routes are missing")
    print("Smoke passed: trusted local TLS, database health, frontend entry/locale and all API families; no user mutations.")


def fclean(env, context, *, confirmation):
    config = json.loads(run(COMPOSE + ["config", "--format", "json"], quiet=True, env=env))
    configured = config.get("volumes") or {}
    volumes = {}
    for logical, details in configured.items():
        require(isinstance(details, dict) and isinstance(details.get("name"), str),
                f"Compose volume {logical} has no resolved name")
        volumes[logical] = details["name"]

    existing = set(run(["docker", "volume", "ls", "--quiet"], quiet=True, env=env).splitlines())
    for logical, name in volumes.items():
        if name not in existing:
            continue
        info = json.loads(run(["docker", "volume", "inspect", name], quiet=True, env=env))[0]
        labels = info.get("Labels") or {}
        require(
            labels.get("com.docker.compose.project") == "task-manager"
            and labels.get("com.docker.compose.volume") == logical,
            f"Refusing to remove volume without matching project labels: {name}",
        )

    images = []
    for name in APP_IMAGES:
        image_id = run(
            ["docker", "image", "ls", "--quiet", "--no-trunc", name],
            quiet=True,
            env=env,
        ).strip()
        if not image_id:
            continue
        info = json.loads(run(["docker", "image", "inspect", name], quiet=True, env=env))[0]
        labels = (info.get("Config") or {}).get("Labels") or {}
        require(
            labels.get("com.docker.compose.project") == "task-manager",
            f"Refusing to remove image without matching project label: {name}",
        )
        images.append(name)

    volume_list = "\n".join(f"  - {name}" for name in volumes.values()) or "  - none"
    prompt = (
        "WARNING: this permanently deletes the project database and uploads.\n"
        f"Docker context: {context!r}\nEndpoint: {env['DOCKER_HOST']!r}\n"
        f"Project volumes:\n{volume_list}\n"
        f"Type {confirmation}: "
    )
    require(input(prompt) == confirmation, "Cleanup cancelled")
    run(COMPOSE + ["--profile", "test", "down", "--volumes", "--rmi", "local"], env=env)
    for name in images:
        remaining = run(
            ["docker", "image", "ls", "--quiet", "--no-trunc", name],
            quiet=True,
            env=env,
        ).strip()
        if remaining:
            run(["docker", "image", "rm", name], env=env)


def main():
    require(len(sys.argv) == 2 and sys.argv[1] in ACTIONS,
            "Usage: dev.py {" + "|".join(sorted(ACTIONS)) + "}")
    action = sys.argv[1]
    if action == "setup":
        setup()
        return
    if action in {"check", "up", "test", "smoke", "reset-db", "re"}:
        env, context = check()
    else:
        env, context = local_docker_env(compose_env())
    if action == "up":
        run(COMPOSE + ["up", "--build", "--detach", "--wait"], env=env)
    elif action in {"down", "clean", "logs", "ps"}:
        args = {"down": ["--profile", "test", "down"],
                "clean": ["--profile", "test", "down"],
                "logs": ["logs", "--follow", "--tail", "100"],
                "ps": ["--profile", "test", "ps"]}
        run(COMPOSE + args[action], env=env)
    elif action == "fclean":
        fclean(env, context, confirmation="fclean")
    elif action == "re":
        fclean(env, context, confirmation="re")
        run(COMPOSE + ["up", "--build", "--detach", "--wait"], env=env)
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
