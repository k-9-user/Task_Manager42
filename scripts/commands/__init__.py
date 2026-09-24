"""Make targets: validate the request, prepare Docker, then run one target."""

import sys

from ..lib import compose, data
from ..lib.process import require
from . import backend_tests, backup, check, cleanup, reset_db, setup, smoke, stack


def deploy(env, context):
    stack.up(env, context)
    smoke.smoke()
    print("Deployed: https://localhost")


TARGETS = {
    "all": (True, deploy),
    "check": (True, lambda env, context: None),
    "up": (True, stack.up),
    "down": (False, stack.down),
    "clean": (False, stack.down),
    "logs": (False, stack.logs),
    "ps": (False, stack.ps),
    "smoke": (True, lambda env, context: smoke.smoke()),
    "test": (True, backend_tests.run_backend_tests),
    "fclean": (False, cleanup.fclean),
    "re": (True, cleanup.rebuild),
    "reset-db": (True, reset_db.reset_database),
    "backup": (True, backup.backup),
    "restore": (True, backup.restore),
}
ACTIONS = {"setup", *TARGETS}


def main():
    require(len(sys.argv) == 2 and sys.argv[1] in ACTIONS, "Usage: make.py {" + "|".join(sorted(ACTIONS)) + "}")
    action = sys.argv[1]

    if action in ("setup", "all"):
        setup.setup()
    if action == "setup":
        return

    data.ensure_data_dirs()
    checked, handler = TARGETS[action]
    env, context = check.check() if checked else compose.local_docker_env(compose.compose_env())
    handler(env, context)
