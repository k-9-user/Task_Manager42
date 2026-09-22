"""Add project_messages table."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "add_project_messages"
down_revision: str | None = "oauth_handoffs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("project_messages")
