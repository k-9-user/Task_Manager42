import json
import re
import shutil

from .core import APP_IMAGES, COMPOSE, DATA, DATA_BACKUPS, DATA_VOLUMES, require, run


def _bound_data_dir(config, logical):
    """Resolve the host directory Compose says a stateful volume is bound to."""

    details = (config.get("volumes") or {}).get(logical) or {}
    device = (details.get("driver_opts") or {}).get("device")
    expected = DATA / DATA_VOLUMES[logical]
    require(device == str(expected), f"Compose volume {logical} is not bound to {expected}; refusing to delete host data")
    require(not expected.is_symlink(), f"{expected} must not be a symlink")
    require(expected.is_dir(), f"{expected} is not a directory")
    resolved = expected.resolve()
    require(resolved.parent == DATA.resolve(), f"Refusing to delete a directory outside {DATA}: {resolved}")
    return resolved


def _clear_data_dir(path):
    """Empty a bound directory while keeping it, so the device stays valid."""

    for entry in path.iterdir():
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()


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
    require(
        re.fullmatch(r"unix:///[^\s?#]+|npipe:////\./pipe/[^\s/?#]+", endpoint),
        "Local Docker endpoint required: only Unix sockets or local named pipes are allowed; TCP/SSH are refused",
    )
    env.pop("DOCKER_CONTEXT", None)
    env["DOCKER_HOST"] = endpoint
    return env, context


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

    data_dirs = [_bound_data_dir(config, logical) for logical in DATA_VOLUMES]

    volume_list = "\n".join(f"  - {name}" for name in volumes.values()) or "  - none"
    directory_list = "\n".join(f"  - {path}" for path in data_dirs)
    prompt = (
        "WARNING: this permanently deletes the project database and uploads.\n"
        f"Docker context: {context!r}\nEndpoint: {env['DOCKER_HOST']!r}\n"
        f"Project volumes:\n{volume_list}\n"
        f"Host directories to erase:\n{directory_list}\n"
        f"Backups in {DATA / DATA_BACKUPS} are kept.\n"
        f"Type {confirmation}: "
    )
    require(input(prompt) == confirmation, "Cleanup cancelled")
    run(COMPOSE + ["--profile", "test", "down", "--volumes", "--rmi", "local"], env=env)
    for path in data_dirs:
        _clear_data_dir(path)
    for name in images:
        remaining = run(
            ["docker", "image", "ls", "--quiet", "--no-trunc", name],
            quiet=True,
            env=env,
        ).strip()
        if remaining:
            run(["docker", "image", "rm", name], env=env)


def reset_database(env, context):
    config = json.loads(run(COMPOSE + ["config", "--format", "json"], quiet=True, env=env))
    volume = config["volumes"]["postgres_data"]["name"]
    data_dir = _bound_data_dir(config, "postgres_data")
    info = json.loads(run(["docker", "volume", "inspect", volume], quiet=True, env=env))[0]
    labels = info.get("Labels") or {}
    require(
        labels.get("com.docker.compose.project") == "task-manager"
        and labels.get("com.docker.compose.volume") == "postgres_data",
        "Refusing to remove a volume without matching project/database labels",
    )
    require(
        input(
            f"Docker context: {context!r}\nEndpoint: {env['DOCKER_HOST']!r}\n"
            f"Delete ONLY volume {volume!r} and erase {str(data_dir)!r}? Type reset-db: "
        ) == "reset-db",
        "Reset cancelled",
    )
    run(COMPOSE + ["stop", "nginx", "backend", "backup", "migrate", "db"], env=env)
    run(COMPOSE + ["rm", "--force", "db"], env=env)
    run(["docker", "volume", "rm", volume], env=env)
    _clear_data_dir(data_dir)
    print("Dev database removed; uploads preserved. Run make up to recreate and migrate.")


def list_backups(postgres_db):
    """Complete backups, oldest first. In-progress ones are dot-prefixed and never match."""

    backups_dir = DATA / DATA_BACKUPS
    require(not backups_dir.is_symlink(), f"{backups_dir} must not be a symlink")
    if not backups_dir.is_dir():
        return []
    pattern = re.compile(re.escape(postgres_db) + r"-[0-9]{8}T[0-9]{6}Z")
    return sorted(
        entry.name for entry in backups_dir.iterdir()
        if entry.is_dir() and not entry.is_symlink() and pattern.fullmatch(entry.name)
    )


def restore_backup(env, context, postgres_db, requested=""):
    """Replace the database and uploads with one backup; the caller restarts the stack."""

    backups = list_backups(postgres_db)
    require(backups, f"No backup in {DATA / DATA_BACKUPS}; run make backup first")
    name = requested or backups[-1]
    require(name in backups, f"Unknown backup {name!r}; latest is {backups[-1]}")
    latest = " (latest)" if name == backups[-1] else ""
    require(
        input(
            "WARNING: this replaces the current database and uploads with a backup.\n"
            f"Docker context: {context!r}\nEndpoint: {env['DOCKER_HOST']!r}\n"
            f"Backup: {name}{latest} ({len(backups)} available)\n"
            "Type restore: "
        ) == "restore",
        "Restore cancelled",
    )
    run(COMPOSE + ["stop", "nginx", "backend", "backup"], env=env)
    run(COMPOSE + ["--profile", "restore", "run", "--rm", "restore", name], env=env)
    return name
