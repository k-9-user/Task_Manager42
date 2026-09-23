from datetime import datetime

from pydantic import BaseModel


class ProgressResponse(BaseModel):
    xp: int
    level: int
    level_xp: int
    next_level_xp: int | None
    badge: str | None


class BadgeResponse(BaseModel):
    key: str
    level: int
    xp: int
    awarded_at: datetime | None


class AchievementResponse(BaseModel):
    key: str
    threshold: int
    xp: int
    unlocked_at: datetime | None


class TrackResponse(BaseModel):
    key: str
    count: int
    recent: int
    achievements: list[AchievementResponse]


class GamificationData(BaseModel):
    progress: ProgressResponse
    daily_cap: int
    badges: list[BadgeResponse]
    tracks: list[TrackResponse]
