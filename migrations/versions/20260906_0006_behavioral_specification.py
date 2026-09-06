"""Add approved behavioral specification and evaluation provenance."""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0006"
down_revision = "20260905_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("approved_versions")
    }
    if "behavioral_specification" not in columns:
        op.add_column(
            "approved_versions", sa.Column("behavioral_specification", sa.JSON(), nullable=True)
        )
    if "evaluation_report" not in columns:
        op.add_column("approved_versions", sa.Column("evaluation_report", sa.JSON(), nullable=True))


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("approved_versions")
    }
    if "evaluation_report" in columns:
        op.drop_column("approved_versions", "evaluation_report")
    if "behavioral_specification" in columns:
        op.drop_column("approved_versions", "behavioral_specification")
