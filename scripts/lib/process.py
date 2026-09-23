"""Precondition and subprocess helpers."""

import shutil
import subprocess

from .paths import ROOT


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(args, *, quiet=False, env=None):
    result = subprocess.run(
        args,
        shell=False,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=quiet,
        check=False,
    )
    require(result.returncode == 0, f"{args[0]} command failed (exit {result.returncode})")
    return result.stdout if quiet else None


def tools(*names):
    for name in names:
        require(shutil.which(name), f"Missing tool: {name}")
