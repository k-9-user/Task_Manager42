from bisect import bisect_right
from dataclasses import dataclass
from enum import StrEnum
from itertools import accumulate


class Track(StrEnum):
    PROJECTS = "projects"
    TASKS_CREATED = "tasks_created"
    TASKS_COMPLETED = "tasks_completed"
    COMMENTS = "comments"
    FILES = "files"
    MESSAGES = "messages"
    COLLABORATORS = "collaborators"


@dataclass(frozen=True)
class Achievement:
    key: str
    track: Track
    threshold: int
    xp: int


@dataclass(frozen=True)
class Badge:
    key: str
    level: int


MAX_LEVEL = 100
LEVEL_BASE_XP = 50
LEVEL_GROWTH = 1.035
TIER_XP = (35, 105, 315, 945, 2835, 8505)
TRACK_THRESHOLDS = {
    Track.PROJECTS: (1, 2, 5, 10, 25),
    Track.TASKS_CREATED: (1, 10, 25, 50, 100, 250),
    Track.TASKS_COMPLETED: (1, 10, 25, 50, 100, 250),
    Track.COMMENTS: (1, 10, 25, 50, 100),
    Track.FILES: (1, 5, 10, 25, 50),
    Track.MESSAGES: (1, 10, 25, 50, 100),
    Track.COLLABORATORS: (1, 3, 5, 10),
}
ACHIEVEMENTS = tuple(
    Achievement(f"{track.value}_{threshold}", track, threshold, TIER_XP[tier])
    for track, thresholds in TRACK_THRESHOLDS.items()
    for tier, threshold in enumerate(thresholds)
)
BADGES = (
    Badge("planner", 5),
    Badge("organizer", 10),
    Badge("achiever", 25),
    Badge("strategist", 50),
    Badge("grandmaster", 100),
)


LEVEL_XP = tuple(
    accumulate(
        (round(LEVEL_BASE_XP * LEVEL_GROWTH**step) for step in range(MAX_LEVEL - 1)),
        initial=0,
    )
)


def level_for(xp: int) -> int:
    return bisect_right(LEVEL_XP, max(xp, 0))


def xp_for_level(level: int) -> int:
    return LEVEL_XP[level - 1]


def badge_for(level: int) -> str | None:
    earned = [badge.key for badge in BADGES if badge.level <= level]
    return earned[-1] if earned else None
