"""make reset-db: confirmed deletion of the development database only."""

import json

from ..lib.compose import COMPOSE
from ..lib.data import bound_data_dir, clear_data_dir
from ..lib.process import require, run


def reset_database(env, context):
    config = json.loads(run(COMPOSE + ["config", "--format", "json"], quiet=True, env=env))
    volume = config["volumes"]["postgres_data"]["name"]
    data_dir = bound_data_dir(config, "postgres_data")
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
    clear_data_dir(data_dir)
    print("Dev database removed; uploads preserved. Run make up to recreate and migrate.")
