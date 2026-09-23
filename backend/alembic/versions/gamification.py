"""Gamification: activity ledger, unlocked achievements and earned badges."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "gamification"
down_revision: str | None = "gdpr_hardening"
branch_labels = None
depends_on = None


def _user_column() -> sa.Column:
    return sa.Column(
        "user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )


def _timestamp_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def upgrade() -> None:
    op.create_table(
        "user_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _user_column(),
        sa.Column("track", sa.String(32), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        _timestamp_column("created_at"),
        sa.UniqueConstraint("user_id", "track", "subject_id", name="uq_user_activity"),
    )
    op.create_table(
        "user_achievements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _user_column(),
        sa.Column("achievement_key", sa.String(64), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False),
        _timestamp_column("unlocked_at"),
        sa.UniqueConstraint("user_id", "achievement_key", name="uq_user_achievement"),
        sa.CheckConstraint("xp > 0", name="ck_user_achievements_xp_positive"),
    )
    op.create_table(
        "user_badges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _user_column(),
        sa.Column("badge_key", sa.String(32), nullable=False),
        _timestamp_column("awarded_at"),
        sa.UniqueConstraint("user_id", "badge_key", name="uq_user_badge"),
    )


def downgrade() -> None:
    op.drop_table("user_badges")
    op.drop_table("user_achievements")
    op.drop_table("user_activities")
