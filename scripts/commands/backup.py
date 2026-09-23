"""make backup and make restore: drive backup/backup.sh through Compose."""

import os

from ..lib.compose import COMPOSE
from ..lib.data import backups_dir, list_backups
from ..lib.env import read_env
from ..lib.paths import ROOT
from ..lib.process import require, run


def backup(env, _context):
    """Take one backup now with the script the scheduled backup service runs."""

    run(COMPOSE + ["run", "--rm", "backup", "once"], env=env)


def restore(env, context):
    postgres_db = read_env(ROOT / ".env")["POSTGRES_DB"]
    name = restore_backup(env, context, postgres_db, os.environ.get("BACKUP", ""))
    print(f"Restored {name}. Verify with make smoke and https://localhost/status.")


def restore_backup(env, context, postgres_db, requested=""):
    """Replace the database and uploads with one backup, then restart the stack.

    A failed restore leaves the live data unchanged, so the stack restarts on it either way.
    """

    backups = list_backups(postgres_db)
    require(backups, f"No backup in {backups_dir()}; run make backup first")
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
    try:
        run(COMPOSE + ["--profile", "restore", "run", "--rm", "restore", name], env=env)
    finally:
        run(COMPOSE + ["up", "--build", "--detach", "--wait"], env=env)
    return name
