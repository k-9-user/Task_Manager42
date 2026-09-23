from datetime import datetime, timezone
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
    Track,
    level_for,
)
from app.services.gamification.progress import total_xp, track_counts


def record_activity(db: Session, user_id: UUID, track: Track, subject_id: UUID) -> None:
    """Count one item for a track, then award what the new totals unlock.

    Runs inside the caller's transaction, right before its commit.
    """

    _lock_user_progress(db, user_id)
    if _already_counted(db, user_id, track, subject_id):
        return
    since = datetime.now(timezone.utc) - DAILY_WINDOW
    if track_counts(db, user_id, since=since).get(track.value, 0) >= DAILY_CAP:
        return

    db.add(UserActivity(user_id=user_id, track=track.value, subject_id=subject_id))
    db.flush()
    _award(db, user_id)


def _lock_user_progress(db: Session, user_id: UUID) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtextextended(f"gamification:{user_id}", 0)
                )
            )
        )


def _already_counted(db: Session, user_id: UUID, track: Track, subject_id: UUID) -> bool:
    return (
        db.scalar(
            select(UserActivity.id).where(
                UserActivity.user_id == user_id,
                UserActivity.track == track.value,
                UserActivity.subject_id == subject_id,
            )
        )
        is not None
    )


def _award(db: Session, user_id: UUID) -> None:
    counts = track_counts(db, user_id)
    unlocked = set(
        db.scalars(
            select(UserAchievement.achievement_key).where(
                UserAchievement.user_id == user_id
            )
        )
    )
    for achievement in ACHIEVEMENTS:
        if (
            achievement.key not in unlocked
            and counts.get(achievement.track.value, 0) >= achievement.threshold
        ):
            db.add(
                UserAchievement(
                    user_id=user_id,
                    achievement_key=achievement.key,
                    xp=achievement.xp,
                )
            )
    db.flush()

    level = level_for(total_xp(db, user_id))
    earned = set(
        db.scalars(select(UserBadge.badge_key).where(UserBadge.user_id == user_id))
    )
    for badge in BADGES:
        if badge.key not in earned and badge.level <= level:
            db.add(UserBadge(user_id=user_id, badge_key=badge.key))
    db.flush()
