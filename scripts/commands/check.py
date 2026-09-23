"""make check: configuration, Docker, TLS and Compose checks run before most targets."""

from ..lib import tls
from ..lib.compose import COMPOSE, compose_env, local_docker_env
from ..lib.config import validate_env
from ..lib.env import read_env
from ..lib.paths import ROOT
from ..lib.process import run, tools


def check():
    validate_env(read_env(ROOT / ".env"))
    tools("docker", "openssl", "curl")
    env, context = local_docker_env(compose_env())
    run(["docker", "compose", "version"], quiet=True, env=env)
    run(["docker", "info"], quiet=True, env=env)
    tls.verify_pair()
    run(COMPOSE + ["--profile", "test", "config", "--quiet"], quiet=True, env=env)
    print("Checks passed: tools, daemon, env, secrets, TLS and Compose (no secrets printed).")
    return env, context
