"""GDPR hardening: membership join time and anonymized attachment uploader."""

import sqlalchemy as sa
from alembic import op


revision: str = "gdpr_hardening"
down_revision: str | None = "add_project_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_members",
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.drop_constraint("attachments_uploaded_by_fkey", "attachments", type_="foreignkey")
    op.alter_column("attachments", "uploaded_by", nullable=True)
    op.create_foreign_key(
        "attachments_uploaded_by_fkey",
        "attachments",
        "users",
        ["uploaded_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("attachments_uploaded_by_fkey", "attachments", type_="foreignkey")
    op.execute(sa.text("DELETE FROM attachments WHERE uploaded_by IS NULL"))
    op.alter_column("attachments", "uploaded_by", nullable=False)
    op.create_foreign_key(
        "attachments_uploaded_by_fkey",
        "attachments",
        "users",
        ["uploaded_by"],
        ["id"],
    )
    op.drop_column("project_members", "joined_at")
