"""make fclean and make re: confirmed removal of project containers, images and data."""

import json

from ..lib.compose import APP_IMAGES, COMPOSE
from ..lib.data import backups_dir, bound_data_dir, clear_data_dir
from ..lib.paths import DATA_VOLUMES
from ..lib.process import require, run


def fclean(env, context, *, confirmation="fclean"):
    config = json.loads(run(COMPOSE + ["config", "--format", "json"], quiet=True, env=env))
    configured = config.get("volumes") or {}
    volumes = {}
    for logical, details in configured.items():
        require(isinstance(details, dict) and isinstance(details.get("name"), str), f"Compose volume {logical} has no resolved name")
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

    data_dirs = [bound_data_dir(config, logical) for logical in DATA_VOLUMES]

    volume_list = "\n".join(f"  - {name}" for name in volumes.values()) or "  - none"
    directory_list = "\n".join(f"  - {path}" for path in data_dirs)
    prompt = (
        "WARNING: this permanently deletes the project database and uploads.\n"
        f"Docker context: {context!r}\nEndpoint: {env['DOCKER_HOST']!r}\n"
        f"Project volumes:\n{volume_list}\n"
        f"Host directories to erase:\n{directory_list}\n"
        f"Backups in {backups_dir()} are kept.\n"
        f"Type {confirmation}: "
    )
    require(input(prompt) == confirmation, "Cleanup cancelled")
    run(COMPOSE + ["--profile", "test", "down", "--volumes", "--rmi", "local"], env=env)
    for path in data_dirs:
        clear_data_dir(path)
    for name in images:
        remaining = run(
            ["docker", "image", "ls", "--quiet", "--no-trunc", name],
            quiet=True,
            env=env,
        ).strip()
        if remaining:
            run(["docker", "image", "rm", name], env=env)


def rebuild(env, context):
    fclean(env, context, confirmation="re")
    run(COMPOSE + ["up", "--build", "--detach", "--wait"], env=env)
