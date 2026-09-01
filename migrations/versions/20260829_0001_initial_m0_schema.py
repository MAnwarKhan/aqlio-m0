"""Create the initial durable Aqlio M0 schema.

Revision ID: 20260829_0001
Revises: None
"""

from collections.abc import Sequence

from alembic import op

from app.infrastructure.db_models import Base

revision: str = "20260829_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the fixed Phase 3 initial schema snapshot."""

    Base.metadata.create_all(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    """Development rollback only; production data must be backed up first."""

    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=False)
