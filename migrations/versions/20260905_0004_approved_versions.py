"""Add immutable approved application-version snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "20260905_0004"
down_revision = "20260830_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "approved_versions" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "approved_versions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("project_version_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("application_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("behavior_config", sa.JSON(), nullable=False),
        sa.Column("ui_config", sa.JSON(), nullable=False),
        sa.Column("document_asset_ids", sa.JSON(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_version_id"], ["project_versions.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_approved_versions_project_id", "approved_versions", ["project_id"])


def downgrade() -> None:
    if "approved_versions" not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_index("ix_approved_versions_project_id", table_name="approved_versions")
    op.drop_table("approved_versions")
