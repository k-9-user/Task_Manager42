"""make up, down, clean, logs and ps: thin Docker Compose wrappers."""

from ..lib.compose import COMPOSE
from ..lib.process import run


def up(env, _context):
    run(COMPOSE + ["up", "--build", "--detach", "--wait"], env=env)


def down(env, _context):
    run(COMPOSE + ["--profile", "test", "down"], env=env)


def logs(env, _context):
    run(COMPOSE + ["logs", "--follow", "--tail", "100"], env=env)


def ps(env, _context):
    run(COMPOSE + ["--profile", "test", "ps"], env=env)
