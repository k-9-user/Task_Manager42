"""Make target implementations and command dispatch."""

import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile

from . import config
from . import docker
from .core import ACTIONS, CERT, CERTS, COMPOSE, KEY, ROOT, require, run, tools


def setup():
    tools("openssl")
    config.setup_configuration()
    require(CERT.exists() == KEY.exists(), "Incomplete TLS pair; restore it or remove both files before setup")
    if CERT.exists():
        print("Preserved existing TLS pair.")
        return

    CERTS.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(CERTS.stat().st_mode & 0o077 == 0, "nginx/certs must be private (chmod 700 nginx/certs)")
    with tempfile.TemporaryDirectory(dir=CERTS) as temporary:
        cert, key = Path(temporary) / "cert", Path(temporary) / "key"
        run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-days", "365", "-subj", "/CN=localhost", "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
            "-keyout", str(key), "-out", str(cert),
        ], quiet=True)

        for source, target in ((cert, CERT), (key, KEY)):
            source.chmod(0o644)
            os.link(source, target)

    print("Created local TLS pair; host trust store unchanged.")


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
    config.validate_env(config.read_env(ROOT / ".env"))
    tools("docker", "openssl", "curl")
    env, context = docker.local_docker_env(config.compose_env())
    run(["docker", "compose", "version"], quiet=True, env=env)
    run(["docker", "info"], quiet=True, env=env)
    require(CERT.is_file() and KEY.is_file() and os.access(CERT, os.R_OK) and os.access(KEY, os.R_OK), "Missing or unreadable TLS pair; run make setup")
    require(CERTS.stat().st_mode & 0o077 == 0, "nginx/certs must be private (chmod 700 nginx/certs)")
    require(all(path.stat().st_mode & 0o004 for path in (CERT, KEY)), "TLS files need read permission for unprivileged nginx inside private nginx/certs")
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
    def get(path, *, with_headers=False):
        output = run([
            "curl", "--fail", "--silent", "--show-error", "--noproxy", "*",
            "--connect-timeout", "5", "--max-time", "15", "--cacert", str(CERT),
        ] + (["--include"] if with_headers else []) + [
            "https://localhost" + path,
        ], quiet=True)
        if not with_headers:
            return output
        for separator in ("\r\n\r\n", "\n\n"):
            headers, found, body = output.partition(separator)
            if found:
                return headers, body
        raise ValueError("Frontend response has no header/body separator")

    def frontend_nonce():
        """Prove the CSP nonce pipeline end to end."""

        headers, body = get("/", with_headers=True)
        require("VITE_CSP_NONCE" not in body, "nginx did not substitute the Vite CSP nonce placeholder")
        policy = re.search(r"(?im)^content-security-policy:.*$", headers)
        require(policy is not None, "Frontend response carries no Content-Security-Policy")
        declared = re.search(r"'nonce-([A-Za-z0-9+/=_-]+)'", policy.group(0))
        require(declared is not None, "Frontend CSP declares no nonce source")
        tags = re.findall(r"<script\b[^>]*>", body)
        require(tags and all('nonce="' in tag for tag in tags), "A script tag is not nonced; it would be blocked by script-src")
        stamped = set(re.findall(r'nonce="([A-Za-z0-9+/=_-]+)"', body))
        require(stamped == {declared.group(1)}, "Vite tag nonces do not match the nonce declared in the CSP header")
        return declared.group(1)

    require(json.loads(get("/health")) == {"status": "ok", "db": "ok"}, "Health check failed")
    root = get("/")
    require('<div id="root">' in root and 'src="/src/main.jsx"' in root, "Frontend root or source entry is missing")
    require(frontend_nonce() != frontend_nonce(), "Frontend CSP nonce is not unique per request")
    entry = get("/src/main.jsx")
    require("/node_modules/.vite/deps/" in entry and "/src/App.jsx" in entry and "createRoot" in entry and "<StrictMode>" not in entry, "Frontend entry is not Vite-transformed JavaScript")
    locale = json.loads(get("/locales/en/translation.json"))
    require(isinstance(locale, dict) and isinstance(locale.get("navbar"), dict) and bool(locale["navbar"].get("projects")), "Frontend English locale is missing")
    paths = json.loads(get("/openapi.json"))["paths"]
    expected = {
        "/health": "get", "/api/auth/login": "post", "/api/auth/register": "post",
        "/api/projects": "get", "/api/tasks/{task_id}": "put",
        "/api/notifications": "get", "/api/search/tasks": "get", "/api/gdpr/export": "get",
        "/api/users/me": "get", "/api/v1/public/tasks": "get", "/api/status": "get",
        "/api/export": "get", "/api/import": "post",
        "/api/tasks/{task_id}/attachments": "post", "/api/attachments/{attachment_id}": "delete",
        "/api/auth/oauth/google/exchange": "post", "/api/api-keys": "post",
        "/api/api-keys/{key_id}/rotate": "post",
    }
    require(all(method in paths.get(path, {}) for path, method in expected.items()), "Expected OpenAPI routes are missing")
    print("Smoke passed: trusted local TLS, database health, per-request frontend CSP nonce, frontend entry/locale and all API families; no user mutations.")


def backup(env):
    """Take one backup now with the script the scheduled backup service runs."""

    run(COMPOSE + ["run", "--rm", "backup", "once"], env=env)


def main():
    require(len(sys.argv) == 2 and sys.argv[1] in ACTIONS, "Usage: make.py {" + "|".join(sorted(ACTIONS)) + "}")
    action = sys.argv[1]

    if action == "setup":
        setup()
        return

    config.ensure_data_dirs()

    if action in {"check", "up", "test", "smoke", "reset-db", "re", "backup", "restore"}:
        env, context = check()
    else:
        env, context = docker.local_docker_env(config.compose_env())

    if action == "up":
        run(COMPOSE + ["up", "--build", "--detach", "--wait"], env=env)

    elif action == "backup":
        backup(env)

    elif action == "restore":
        postgres_db = config.read_env(ROOT / ".env")["POSTGRES_DB"]
        name = docker.restore_backup(env, context, postgres_db, os.environ.get("BACKUP", ""))
        run(COMPOSE + ["up", "--build", "--detach", "--wait"], env=env)
        print(f"Restored {name}. Verify with make smoke and https://localhost/status.")

    elif action in {"down", "clean", "logs", "ps"}:
        args = {
            "down": ["--profile", "test", "down"],
            "clean": ["--profile", "test", "down"],
            "logs": ["logs", "--follow", "--tail", "100"],
            "ps": ["--profile", "test", "ps"],
        }
        run(COMPOSE + args[action], env=env)

    elif action == "fclean":
        docker.fclean(env, context, confirmation="fclean")

    elif action == "re":
        docker.fclean(env, context, confirmation="re")
        run(COMPOSE + ["up", "--build", "--detach", "--wait"], env=env)

    elif action == "smoke":
        smoke()

    elif action == "test":
        run(COMPOSE + ["--profile", "test", "build", "test"], env=env)
        try:
            run(COMPOSE + ["--profile", "test", "run", "--rm", "test", "python", "-m", "pytest", "-q"] + shlex.split(os.environ.get("TESTS", "")), env=env)
        finally:
            run(COMPOSE + ["--profile", "test", "rm", "--stop", "--force", "test-db"], env=env)

    elif action == "reset-db":
        docker.reset_database(env, context)
