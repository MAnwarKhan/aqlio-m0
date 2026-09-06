"""Snapshot participant-validation evidence with approved versions."""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0007"
down_revision = "20260906_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("approved_versions")
    }
    if "participant_validation" not in columns:
        op.add_column(
            "approved_versions", sa.Column("participant_validation", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("approved_versions")
    }
    if "participant_validation" in columns:
        op.drop_column("approved_versions", "participant_validation")
