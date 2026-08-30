"""Relational persistence model for the approved M0 domain."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    identity_provider: Mapped[str | None] = mapped_column(String(40))
    identity_subject: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("identity_provider", "identity_subject", name="uq_user_provider_subject"),
    )


class WorkspaceRow(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkspaceMemberRow(Base):
    __tablename__ = "workspace_members"
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_workspace_member_user_workspace", "user_id", "workspace_id"),)


class ProjectRow(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500), default="")
    journey_metadata: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), index=True)
    valid_document_count: Mapped[int] = mapped_column(Integer, default=0)
    prepared_document_count: Mapped[int] = mapped_column(Integer, default=0)
    guided_test_count: Mapped[int] = mapped_column(Integer, default=0)
    has_blocking_preparation_error: Mapped[bool] = mapped_column(Boolean, default=False)
    readiness_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    current_version_id: Mapped[str | None] = mapped_column(String(64), index=True)
    template: Mapped[str] = mapped_column(String(50), default="ASK_MY_DOCUMENTS")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_project_workspace_owner", "workspace_id", "owner_user_id"),)


class ProjectVersionRow(Base):
    __tablename__ = "project_versions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)
    template: Mapped[str] = mapped_column(String(50))
    policy: Mapped[str] = mapped_column(String(50))
    assistant_config: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("project_id", "number", name="uq_project_version_number"),)


class ProjectVersionAssetRow(Base):
    __tablename__ = "project_version_assets"
    project_version_id: Mapped[str] = mapped_column(
        ForeignKey("project_versions.id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[str] = mapped_column(String(64), primary_key=True)


class AssetRow(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    original_name: Mapped[str] = mapped_column(String(255))
    safe_name: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(150))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    participant_message: Mapped[str | None] = mapped_column(String(500))
    normalized_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("project_id", "checksum", name="uq_asset_project_checksum"),
        Index("ix_asset_workspace_project", "workspace_id", "project_id"),
    )


class IngestionJobRow(Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    error_category: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DocumentChunkRow(Base):
    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    project_version_id: Mapped[str] = mapped_column(
        ForeignKey("project_versions.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    source_name: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    __table_args__ = (Index("ix_chunk_scope", "workspace_id", "project_id", "project_version_id"),)


class GuidedTestRow(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    project_version_id: Mapped[str] = mapped_column(ForeignKey("project_versions.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    question_summary: Mapped[str] = mapped_column(String(64))
    cited_asset_ids: Mapped[str] = mapped_column(Text)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AIRunRow(Base):
    __tablename__ = "ai_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    correlation_id: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    error_category: Mapped[str | None] = mapped_column(String(80))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UsageEventRow(Base):
    __tablename__ = "usage_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    operation: Mapped[str] = mapped_column(String(50))
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30))
    request_units: Mapped[int] = mapped_column(Integer)
    estimated_cost: Mapped[float] = mapped_column(Float)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    output_units: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_category: Mapped[str | None] = mapped_column(String(80))
    cost_is_estimated: Mapped[bool] = mapped_column(Boolean, default=True)


class UsageAllowanceRow(Base):
    __tablename__ = "usage_allowances"
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    daily_request_limit: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LifecycleEventRow(Base):
    __tablename__ = "lifecycle_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    asset_id: Mapped[str | None] = mapped_column(String(64))
    publication_id: Mapped[str | None] = mapped_column(String(64))


class PublicationRow(Base):
    __tablename__ = "publications"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    project_version_id: Mapped[str] = mapped_column(ForeignKey("project_versions.id"))
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    project_name: Mapped[str] = mapped_column(String(100))
    template: Mapped[str] = mapped_column(String(50))
    policy: Mapped[str] = mapped_column(String(50))
    assistant_config: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)


class PublicationAssetRow(Base):
    __tablename__ = "publication_assets"
    publication_id: Mapped[str] = mapped_column(
        ForeignKey("publications.id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[str] = mapped_column(String(64), primary_key=True)


class PublicationChunkRow(Base):
    __tablename__ = "publication_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    publication_id: Mapped[str] = mapped_column(
        ForeignKey("publications.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[str] = mapped_column(String(64))
    source_name: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)


class ShareLinkRow(Base):
    __tablename__ = "share_links"
    publication_id: Mapped[str] = mapped_column(
        ForeignKey("publications.id", ondelete="CASCADE"), primary_key=True
    )
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    visibility: Mapped[str] = mapped_column(String(30), index=True)
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str] = mapped_column(String(30))


class RateLimitEventRow(Base):
    __tablename__ = "rate_limit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_key: Mapped[str] = mapped_column(String(160), index=True)
    operation: Mapped[str] = mapped_column(String(50), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
