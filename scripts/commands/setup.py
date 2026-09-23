"""make setup: create or migrate .env, the secret files and the TLS pair."""

import secrets

from ..lib import tls
from ..lib.config import validate_config
from ..lib.env import ADDED_ENV_NAMES, ENV_NAMES, LEGACY_LOCAL_URLS, LOCAL_URLS, read_env, write_env
from ..lib.paths import ROOT
from ..lib.process import require, tools
from ..lib.secret_files import (
    LEGACY_SECRET_NAMES,
    SECRET_NAMES,
    generate_secrets,
    payload_entries,
    read_secret,
    read_secret_files,
    write_secret,
)


def setup():
    tools("openssl")
    setup_configuration()
    tls.create_pair()


def _migrate_local_urls(values):
    configured = {name: values.get(name) for name in LOCAL_URLS}
    if configured == LEGACY_LOCAL_URLS:
        return values | LOCAL_URLS, True
    require(
        configured == LOCAL_URLS,
        "Existing .env has mixed or custom local URLs; set OAuth, CORS and frontend URLs together",
    )
    return values, False


def setup_configuration(root=ROOT):
    env_example = root / ".env.example"
    env_path = root / ".env"
    secret_dir = root / "secrets"
    template = env_example.read_text()
    example_values = read_env(env_example)
    require(set(example_values) == set(ENV_NAMES), ".env.example does not match the supported configuration keys")

    secret_dir.mkdir(mode=0o700, exist_ok=True)
    secret_dir.chmod(0o700)
    existing_entries = payload_entries(secret_dir)

    if not env_path.exists():
        require(not existing_entries, "Secret files exist without .env; restore matching configuration")
        env_values = example_values
        secret_values = generate_secrets(env_values)
        validate_config(env_values, secret_values)
        for name, value in secret_values.items():
            write_secret(secret_dir / name, value)
        write_env(env_path, template, env_values)
        print("Created .env and private file-backed secrets.")
        return

    current = read_env(env_path)
    legacy_keys = set(current) & set(LEGACY_SECRET_NAMES)
    if not legacy_keys:
        missing = set(ENV_NAMES) - set(current)
        require(set(current) <= set(ENV_NAMES) and missing <= set(ADDED_ENV_NAMES),
                ".env must contain exactly the documented non-secret keys")
        current = current | {name: example_values[name] for name in missing}
        current, migrated = _migrate_local_urls(current)
        validate_config(current, read_secret_files(secret_dir))
        if migrated or missing:
            write_env(env_path, template, current)
        if migrated:
            print("Migrated local URLs to default HTTPS ports; preserved secret files.")
        if missing:
            print("Added default backup settings to .env; preserved secret files.")
        if not migrated and not missing:
            print("Preserved existing .env and secret files.")
        return

    expected_legacy = (set(ENV_NAMES) - {"BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_USERNAME"}
                       - set(ADDED_ENV_NAMES)) | set(LEGACY_SECRET_NAMES)
    require(expected_legacy <= set(current) <= expected_legacy | set(ADDED_ENV_NAMES),
            "Legacy .env must be complete before secret migration")
    env_values = {
        name: current.get(name, example_values[name])
        for name in ENV_NAMES
    }
    env_values, _ = _migrate_local_urls(env_values)
    secret_values = {
        new_name: current[old_name]
        for old_name, new_name in LEGACY_SECRET_NAMES.items()
    }
    existing = {entry.name: entry for entry in existing_entries}
    unexpected = set(existing) - set(SECRET_NAMES)
    require(not unexpected, "secrets contains unexpected secret files")
    admin_path = secret_dir / "bootstrap_admin_password"
    if admin_path.exists():
        secret_values["bootstrap_admin_password"] = read_secret(admin_path)
    else:
        secret_values["bootstrap_admin_password"] = secrets.token_urlsafe(36)
    validate_config(env_values, secret_values)
    for name, value in secret_values.items():
        path = secret_dir / name
        if path.exists():
            require(read_secret(path) == value,
                    f"Secret file {name} conflicts with legacy .env; nothing was overwritten")
        else:
            write_secret(path, value)
    write_env(env_path, template, env_values)
    print("Migrated legacy .env secrets into private files.")
