"""Initial database installation migration.
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


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=True),
        sa.Column("oauth_provider", sa.String(), nullable=True),
        sa.Column("oauth_id", sa.String(), nullable=True),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column(
            "role",
            user_role,
            nullable=False,
            server_default=sa.text("'user'"),
        ),
        sa.Column(
            "avatar_url",
            sa.String(),
            nullable=False,
            server_default=sa.text("'/static/default-avatar.png'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "oauth_provider IS NULL OR oauth_provider IN ('google', 'github')",
            name="ck_users_oauth_provider",
        ),
        sa.CheckConstraint(
            "(oauth_provider IS NULL AND oauth_id IS NULL) OR "
            "(oauth_provider IS NOT NULL AND oauth_id IS NOT NULL)",
            name="ck_users_oauth_pair",
        ),
        sa.CheckConstraint(
            "password_hash IS NOT NULL OR "
            "(oauth_provider IS NOT NULL AND oauth_id IS NOT NULL)",
            name="ck_users_auth_method",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint(
            "oauth_provider",
            "oauth_id",
            name="uq_users_oauth_identity",
        ),
    )


def downgrade() -> None:
    op.drop_table("users")
    user_role.drop(op.get_bind(), checkfirst=True)
