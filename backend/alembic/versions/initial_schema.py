"""Initial schema: every table, enum, constraint and index of the application.

Revision ID: initial_schema
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = postgresql.ENUM("admin", "user", name="user_role", create_type=False)
user_status = postgresql.ENUM("active", "banned", name="user_status", create_type=False)
project_role = postgresql.ENUM("owner", "editor", "viewer", name="projectrole", create_type=False)
task_status = postgresql.ENUM("todo", "in_progress", "done", name="taskstatus", create_type=False)
notification_type = postgresql.ENUM(
    "task_assigned", "task_status_changed", "project_invite",
    name="notificationtype", create_type=False,
)
ENUMS = (user_role, user_status, project_role, task_status, notification_type)


def _id() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True)


def _fk(name: str, table: str, ondelete: str | None = "CASCADE", nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(f"{table}.id", ondelete=ondelete),
        nullable=nullable,
    )


def _now(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"))


def upgrade() -> None:
    for enum_type in ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=True),
        sa.Column("oauth_provider", sa.String(), nullable=True),
        sa.Column("oauth_id", sa.String(), nullable=True),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("status", user_status, nullable=False, server_default=sa.text("'active'")),
        sa.Column("role", user_role, nullable=False, server_default=sa.text("'user'")),
        sa.Column(
            "avatar_url", sa.String(), nullable=False,
            server_default=sa.text("'/static/default-avatar.png'"),
        ),
        _now("created_at"),
        _now("updated_at"),
        sa.CheckConstraint(
            "oauth_provider IS NULL OR oauth_provider = 'google'",
            name="ck_users_oauth_provider",
        ),
        sa.CheckConstraint(
            "(oauth_provider IS NULL AND oauth_id IS NULL) OR "
            "(oauth_provider IS NOT NULL AND oauth_id IS NOT NULL)",
            name="ck_users_oauth_pair",
        ),
        sa.CheckConstraint(
            "password_hash IS NOT NULL OR (oauth_provider IS NOT NULL AND oauth_id IS NOT NULL)",
            name="ck_users_auth_method",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("oauth_provider", "oauth_id", name="uq_users_oauth_identity"),
    )
    op.create_index("uq_users_username_lower", "users", [sa.text("lower(username)")], unique=True)

    op.create_table(
        "projects",
        _id(),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        _fk("owner_id", "users", ondelete=None),
        _now("created_at"),
    )
    op.create_table(
        "project_members",
        _id(),
        _fk("project_id", "projects"),
        _fk("user_id", "users"),
        sa.Column("role", project_role, nullable=False),
        _now("joined_at"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )
    op.create_table(
        "tasks",
        _id(),
        _fk("project_id", "projects"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", task_status, nullable=False),
        _fk("assignee_id", "users", "SET NULL", nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("banner_url", sa.String(), nullable=True),
        _now("created_at"),
        _now("updated_at"),
    )
    op.create_table(
        "notifications",
        _id(),
        _fk("user_id", "users"),
        sa.Column("type", notification_type, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        _fk("related_task_id", "tasks", "SET NULL", nullable=True),
        _fk("related_project_id", "projects", "SET NULL", nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False),
        _now("created_at"),
    )
    op.create_table(
        "attachments",
        _id(),
        _fk("task_id", "tasks"),
        sa.Column("file_url", sa.String(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        _fk("uploaded_by", "users", "SET NULL", nullable=True),
        _now("created_at"),
    )
    op.create_table(
        "api_keys",
        _id(),
        _fk("user_id", "users"),
        sa.Column("key_hash", sa.String(), nullable=False, unique=True),
        _now("created_at"),
    )
    op.create_table(
        "comments",
        _id(),
        _fk("task_id", "tasks"),
        _fk("author_id", "users"),
        sa.Column("content", sa.Text(), nullable=False),
        _now("created_at"),
        _now("updated_at"),
    )
    op.create_table(
        "project_messages",
        _id(),
        _fk("project_id", "projects"),
        _fk("author_id", "users"),
        sa.Column("content", sa.Text(), nullable=False),
        _now("created_at"),
    )
    op.create_table(
        "user_activities",
        _id(),
        _fk("user_id", "users"),
        sa.Column("track", sa.String(32), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        _now("created_at"),
        sa.UniqueConstraint("user_id", "track", "subject_id", name="uq_user_activity"),
    )
    op.create_table(
        "user_achievements",
        _id(),
        _fk("user_id", "users"),
        sa.Column("achievement_key", sa.String(64), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False),
        _now("unlocked_at"),
        sa.UniqueConstraint("user_id", "achievement_key", name="uq_user_achievement"),
        sa.CheckConstraint("xp > 0", name="ck_user_achievements_xp_positive"),
    )
    op.create_table(
        "user_badges",
        _id(),
        _fk("user_id", "users"),
        sa.Column("badge_key", sa.String(32), nullable=False),
        _now("awarded_at"),
        sa.UniqueConstraint("user_id", "badge_key", name="uq_user_badge"),
    )


def downgrade() -> None:
    for table in (
        "user_badges", "user_achievements", "user_activities", "project_messages",
        "comments", "api_keys", "attachments", "notifications",
        "tasks", "project_members", "projects", "users",
    ):
        op.drop_table(table)
    for enum_type in reversed(ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
