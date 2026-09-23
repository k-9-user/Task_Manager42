from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user_achievement import UserAchievement
from app.models.user_activity import UserActivity
from app.models.user_badge import UserBadge
from app.services.gamification.catalog import (
    ACHIEVEMENTS,
    BADGES,
    DAILY_CAP,
    DAILY_WINDOW,
    MAX_LEVEL,
    Track,
    badge_for,
    level_for,
    xp_for_level,
)


@dataclass(frozen=True)
class Rank:
    level: int
    badge: str | None


def track_counts(
    db: Session, user_id: UUID, since: datetime | None = None
) -> dict[str, int]:
    query = (
        select(UserActivity.track, func.count())
        .where(UserActivity.user_id == user_id)
        .group_by(UserActivity.track)
    )
    if since is not None:
        query = query.where(UserActivity.created_at >= since)
    return dict(db.execute(query).all())


def total_xp(db: Session, user_id: UUID) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(UserAchievement.xp), 0)).where(
            UserAchievement.user_id == user_id
        )
    )


def ranks_for(db: Session, user_ids: Iterable[UUID]) -> dict[UUID, Rank]:
    ids = set(user_ids)
    xp_by_user = dict(
        db.execute(
            select(UserAchievement.user_id, func.sum(UserAchievement.xp))
            .where(UserAchievement.user_id.in_(ids))
            .group_by(UserAchievement.user_id)
        ).all()
    )
    ranks = {}
    for user_id in ids:
        level = level_for(xp_by_user.get(user_id, 0))
        ranks[user_id] = Rank(level=level, badge=badge_for(level))
    return ranks


def build_summary(db: Session, user_id: UUID) -> dict[str, Any]:
    unlocked = {
        row.achievement_key: row
        for row in db.scalars(
            select(UserAchievement).where(UserAchievement.user_id == user_id)
        )
    }
    awarded = {
        row.badge_key: row.awarded_at
        for row in db.scalars(select(UserBadge).where(UserBadge.user_id == user_id))
    }
    counts = track_counts(db, user_id)
    recent = track_counts(db, user_id, since=datetime.now(timezone.utc) - DAILY_WINDOW)
    xp = sum(row.xp for row in unlocked.values())
    level = level_for(xp)

    return {
        "progress": {
            "xp": xp,
            "level": level,
            "level_xp": xp_for_level(level),
            "next_level_xp": xp_for_level(level + 1) if level < MAX_LEVEL else None,
            "badge": badge_for(level),
        },
        "daily_cap": DAILY_CAP,
        "badges": [
            {
                "key": badge.key,
                "level": badge.level,
                "xp": xp_for_level(badge.level),
                "awarded_at": awarded.get(badge.key),
            }
            for badge in BADGES
        ],
        "tracks": [
            {
                "key": track.value,
                "count": counts.get(track.value, 0),
                "recent": recent.get(track.value, 0),
                "achievements": [
                    {
                        "key": achievement.key,
                        "threshold": achievement.threshold,
                        "xp": achievement.xp,
                        "unlocked_at": (
                            unlocked[achievement.key].unlocked_at
                            if achievement.key in unlocked
                            else None
                        ),
                    }
                    for achievement in ACHIEVEMENTS
                    if achievement.track is track
                ],
            }
            for track in Track
        ],
    }
