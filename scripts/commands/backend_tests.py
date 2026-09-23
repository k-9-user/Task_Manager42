"""make test: run pytest in the isolated test profile."""

import os
import shlex

from ..lib.compose import COMPOSE
from ..lib.process import run


def run_backend_tests(env, _context):
    run(COMPOSE + ["--profile", "test", "build", "test"], env=env)
    try:
        run(COMPOSE + ["--profile", "test", "run", "--rm", "test", "python", "-m", "pytest", "-q"] + shlex.split(os.environ.get("TESTS", "")), env=env)
    finally:
        run(COMPOSE + ["--profile", "test", "rm", "--stop", "--force", "test-db"], env=env)
