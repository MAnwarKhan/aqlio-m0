"""Preserve physical PDF pages in drafts and immutable publication snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0008"
down_revision = "20260906_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, name, kind in (
        ("assets", "page_texts", sa.JSON()),
        ("document_chunks", "page_number", sa.Integer()),
        ("publication_chunks", "page_number", sa.Integer()),
    ):
        existing = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
        if name not in existing:
            op.add_column(table, sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    for table, name in (
        ("publication_chunks", "page_number"),
        ("document_chunks", "page_number"),
        ("assets", "page_texts"),
    ):
        with op.batch_alter_table(table) as batch:
            batch.drop_column(name)
