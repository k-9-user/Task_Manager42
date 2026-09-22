"""Complete initial schema for a fresh, disposable development database.

Upgrading it to head will NOT replay this file.
Revision ID: db_install
Revises:
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "db_install"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = postgresql.ENUM("admin", "user", name="user_role", create_type=False)
user_status = postgresql.ENUM("active", "banned", name="user_status", create_type=False)
project_role = postgresql.ENUM("owner", "editor", "viewer", name="projectrole", create_type=False)
task_status = postgresql.ENUM("todo", "in_progress", "done", name="taskstatus", create_type=False)
notification_type = postgresql.ENUM("task_assigned", "task_status_changed", "project_invite", name="notificationtype", create_type=False)


def upgrade() -> None:
    for enum_type in (user_role, user_status, project_role, task_status, notification_type):
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
        sa.Column("avatar_url", sa.String(), nullable=False, server_default=sa.text("'/static/default-avatar.png'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("oauth_provider IS NULL OR oauth_provider IN ('google', 'github')", name="ck_users_oauth_provider"),
        sa.CheckConstraint("(oauth_provider IS NULL AND oauth_id IS NULL) OR ""(oauth_provider IS NOT NULL AND oauth_id IS NOT NULL)", name="ck_users_oauth_pair"),
        sa.CheckConstraint("password_hash IS NOT NULL OR ""(oauth_provider IS NOT NULL AND oauth_id IS NOT NULL)", name="ck_users_auth_method"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("oauth_provider", "oauth_id", name="uq_users_oauth_identity"),
    )
    op.create_index("uq_users_username_lower", "users", [sa.text("lower(username)")], unique=True)
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "project_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", project_role, nullable=False),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", task_status, nullable=False),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", notification_type, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("related_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("related_project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("file_url", sa.String(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("attachments")
    op.drop_table("notifications")
    op.drop_table("tasks")
    op.drop_table("project_members")
    op.drop_table("projects")
    op.drop_table("users")
    for enum_type in (notification_type, task_status, project_role, user_status, user_role):
        enum_type.drop(op.get_bind(), checkfirst=True)
