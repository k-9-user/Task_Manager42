"""Host data directories: creation, guarded erasure and the backup listing."""

import re
import shutil

from .paths import DATA, DATA_BACKUPS, DATA_DIRS, DATA_VOLUMES
from .process import require


def backups_dir():
    return DATA / DATA_BACKUPS


def ensure_data_dirs(data=DATA):
    """Create the host directories the stateful Compose volumes and backups bind to."""

    require(not data.is_symlink(), f"{data.name} must not be a symlink")
    require(not data.exists() or data.is_dir(), f"{data.name} exists but is not a directory")
    for name in DATA_DIRS + (DATA_BACKUPS,):
        path = data / name
        require(not path.is_symlink(), f"{data.name}/{name} must not be a symlink")
        require(not path.exists() or path.is_dir(), f"{data.name}/{name} exists but is not a directory")
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return data


def bound_data_dir(config, logical):
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


def clear_data_dir(path):
    """Empty a bound directory while keeping it, so the device stays valid."""

    for entry in path.iterdir():
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def list_backups(postgres_db):
    """Complete backups, oldest first: both archives present as regular files."""

    directory = backups_dir()
    require(not directory.is_symlink(), f"{directory} must not be a symlink")
    if not directory.is_dir():
        return []
    pattern = re.compile(re.escape(postgres_db) + r"-[0-9]{8}T[0-9]{6}Z")
    return sorted(
        entry.name for entry in directory.iterdir()
        if entry.is_dir()
        and not entry.is_symlink()
        and pattern.fullmatch(entry.name)
        and all((entry / part).is_file() and not (entry / part).is_symlink()
                for part in ("database.sql.gz", "uploads.tar.gz"))
    )
