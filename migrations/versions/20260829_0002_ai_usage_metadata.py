"""Add managed provider usage and failure metadata.

Revision ID: 20260829_0002
Revises: 20260829_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0002"
down_revision: str | None = "20260829_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("usage_events")}
    with op.batch_alter_table("usage_events") as batch:
        if "output_units" not in existing:
            batch.add_column(
                sa.Column("output_units", sa.Integer(), nullable=False, server_default="0")
            )
        if "latency_ms" not in existing:
            batch.add_column(
                sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0")
            )
        if "retry_count" not in existing:
            batch.add_column(
                sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0")
            )
        if "error_category" not in existing:
            batch.add_column(sa.Column("error_category", sa.String(length=80), nullable=True))
        if "cost_is_estimated" not in existing:
            batch.add_column(
                sa.Column(
                    "cost_is_estimated", sa.Boolean(), nullable=False, server_default=sa.true()
                )
            )


def downgrade() -> None:
    with op.batch_alter_table("usage_events") as batch:
        batch.drop_column("cost_is_estimated")
        batch.drop_column("error_category")
        batch.drop_column("retry_count")
        batch.drop_column("latency_ms")
        batch.drop_column("output_units")
