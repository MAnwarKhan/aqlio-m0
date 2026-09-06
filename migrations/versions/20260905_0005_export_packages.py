"""Add immutable source-code export package records."""

import sqlalchemy as sa
from alembic import op

revision = "20260905_0005"
down_revision = "20260905_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "export_packages" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "export_packages",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("approved_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("project_version_id", sa.String(length=64), nullable=False),
        sa.Column("export_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False, unique=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["approved_snapshot_id"], ["approved_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_version_id"], ["project_versions.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("project_id", "export_version", name="uq_project_export_version"),
    )
    op.create_index(
        "ix_export_packages_approved_snapshot_id", "export_packages", ["approved_snapshot_id"]
    )
    op.create_index("ix_export_packages_project_id", "export_packages", ["project_id"])


def downgrade() -> None:
    if "export_packages" not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_index("ix_export_packages_project_id", table_name="export_packages")
    op.drop_index("ix_export_packages_approved_snapshot_id", table_name="export_packages")
    op.drop_table("export_packages")
