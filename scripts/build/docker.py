import json
import re

from .core import APP_IMAGES, COMPOSE, require, run


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


def reset_database(env, context):
    config = json.loads(run(COMPOSE + ["config", "--format", "json"], quiet=True, env=env))
    volume = config["volumes"]["postgres_data"]["name"]
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
            f"Delete ONLY volume {volume!r}? Type reset-db: "
        ) == "reset-db",
        "Reset cancelled",
    )
    run(COMPOSE + ["stop", "nginx", "backend", "migrate", "db"], env=env)
    run(COMPOSE + ["rm", "--force", "db"], env=env)
    run(["docker", "volume", "rm", volume], env=env)
    print("Dev database removed; uploads preserved. Run make up to recreate and migrate.")
