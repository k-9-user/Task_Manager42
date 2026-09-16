"""Store only hashes of API keys."""

import hashlib

import sqlalchemy as sa
from alembic import op


revision: str = "hash_api_keys"
down_revision: str | None = "add_banner_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, key FROM api_keys")).mappings()
    for row in rows:
        digest = hashlib.sha256(row["key"].encode("utf-8")).hexdigest()
        connection.execute(
            sa.text("UPDATE api_keys SET key = :digest WHERE id = :id"),
            {"digest": digest, "id": row["id"]},
        )
    op.alter_column("api_keys", "key", new_column_name="key_hash")


def downgrade() -> None:
    # Hashes cannot safely be converted back to plaintext or accepted as raw keys.
    op.execute(sa.text("DELETE FROM api_keys"))
    op.alter_column("api_keys", "key_hash", new_column_name="key")
