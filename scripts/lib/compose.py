"""Docker Compose invocation: command prefix, environment and local endpoint."""

import json
import os
import re

from .env import read_env
from .paths import DATA, ROOT
from .process import require, run
from .secret_files import SECRET_ENV_NAMES


COMPOSE = [
    "docker", "compose", "--project-name", "task-manager", "--file",
    str(ROOT / "docker-compose.yml"), "--env-file", str(ROOT / ".env"),
]
APP_IMAGES = ("task-manager-back:latest", "task-manager-front:latest")


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
    env["DATA_DIR"] = str(DATA)
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
    require(
        re.fullmatch(r"unix:///[^\s?#]+|npipe:////\./pipe/[^\s/?#]+", endpoint),
        "Local Docker endpoint required: only Unix sockets or local named pipes are allowed; TCP/SSH are refused",
    )
    env.pop("DOCKER_CONTEXT", None)
    env["DOCKER_HOST"] = endpoint
    return env, context
