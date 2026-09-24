"""Attachments follow their task: deleting a task deletes its attachment rows."""

from alembic import op


revision: str = "attachment_task_cascade"
down_revision: str | None = "gamification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("attachments_task_id_fkey", "attachments", type_="foreignkey")
    op.create_foreign_key(
        "attachments_task_id_fkey",
        "attachments",
        "tasks",
        ["task_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("attachments_task_id_fkey", "attachments", type_="foreignkey")
    op.create_foreign_key(
        "attachments_task_id_fkey",
        "attachments",
        "tasks",
        ["task_id"],
        ["id"],
    )
