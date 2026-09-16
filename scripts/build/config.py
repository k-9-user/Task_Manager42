"""Non-secret environment and file-backed secret lifecycle."""

import ipaddress
import os
import re
import secrets
import stat
import sys
import tempfile

from .core import (
    ENV_NAMES,
    LEGACY_LOCAL_URLS,
    LEGACY_SECRET_NAMES,
    LOCAL_URLS,
    ROOT,
    SECRET_ENV_NAMES,
    SECRET_METADATA,
    SECRET_NAMES,
    SECRETS,
    require,
)


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


def _migrate_local_urls(values):
    configured = {name: values.get(name) for name in LOCAL_URLS}
    if configured == LEGACY_LOCAL_URLS:
        return values | LOCAL_URLS, True
    require(
        configured == LOCAL_URLS,
        "Existing .env has mixed or custom local URLs; set OAuth, CORS and frontend URLs together",
    )
    return values, False


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
        require(values[name] == "https://localhost", f"{name} must be https://localhost")
    for name in ("JWT_EXPIRATION", "MAX_UPLOAD_SIZE_MB"):
        require(re.fullmatch(r"[0-9]+", values[name]) and values[name].lstrip("0"),
                f"{name} must be a positive integer")
    require(values["UPLOAD_DIR"] == "/app/uploads", "UPLOAD_DIR must be /app/uploads for persistent storage")
    require(values["OAUTH_GOOGLE_REDIRECT_URI"] == "https://localhost/api/auth/oauth/google/callback",
            "OAUTH_GOOGLE_REDIRECT_URI must be https://localhost/api/auth/oauth/google/callback")
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
    require(set(example_values) == set(ENV_NAMES), ".env.example does not match the supported configuration keys")

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
        require(set(current) == set(ENV_NAMES), ".env must contain exactly the documented non-secret keys")
        current, migrated = _migrate_local_urls(current)
        validate_config(current, read_secret_files(secret_dir))
        if migrated:
            _write_env(env_path, template, current)
            print("Migrated local URLs to default HTTPS ports; preserved secret files.")
        else:
            print("Preserved existing .env and secret files.")
        return

    expected_legacy = (set(ENV_NAMES) - {"BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_USERNAME"}) \
        | set(LEGACY_SECRET_NAMES)
    require(set(current) == expected_legacy, "Legacy .env must be complete before secret migration")
    env_values = {
        name: current.get(name, example_values[name])
        for name in ENV_NAMES
    }
    env_values, _ = _migrate_local_urls(env_values)
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
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("COMPOSE_") and key not in allowed and key not in SECRET_ENV_NAMES
    }
    env.update(values)
    return env
