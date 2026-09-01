"""Preserve extensible journey metadata and immutable template configuration."""

import sqlalchemy as sa
from alembic import op

revision = "20260830_0003"
down_revision = "20260829_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, column in (
        ("projects", "journey_metadata"),
        ("project_versions", "assistant_config"),
        ("publications", "assistant_config"),
    ):
        existing = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
        # Initial migration creates current metadata on fresh installations.
        if column not in existing:
            op.add_column(table, sa.Column(column, sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    for table, column in (
        ("publications", "assistant_config"),
        ("project_versions", "assistant_config"),
        ("projects", "journey_metadata"),
    ):
        with op.batch_alter_table(table) as batch:
            batch.drop_column(column)
