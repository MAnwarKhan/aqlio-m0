"""Core Aqlio M0 domain records without framework dependencies."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType


class ProjectStatus(StrEnum):
    DRAFT = "DRAFT"
    DOCUMENTS_ADDED = "DOCUMENTS_ADDED"
    PREPARED = "PREPARED"
    TESTED = "TESTED"
    READY = "READY"
    DEPLOYED = "DEPLOYED"
    ARCHIVED = "ARCHIVED"


class WorkspaceRole(StrEnum):
    OWNER = "OWNER"
    MEMBER = "MEMBER"
    ADMIN = "ADMIN"


class AssetStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PREPARING = "PREPARING"
    READY = "READY"
    FAILED = "FAILED"


class PublicationVisibility(StrEnum):
    PRIVATE = "PRIVATE"
    LINK_ONLY = "LINK_ONLY"
    REVOKED = "REVOKED"


@dataclass(frozen=True, slots=True)
class User:
    id: str
    email: str
    display_name: str
    active: bool = True


@dataclass(frozen=True, slots=True)
class Workspace:
    id: str
    owner_user_id: str
    name: str


@dataclass(frozen=True, slots=True)
class WorkspaceMember:
    workspace_id: str
    user_id: str
    role: WorkspaceRole


@dataclass(slots=True)
class Project:
    id: str
    workspace_id: str
    owner_user_id: str
    name: str
    status: ProjectStatus = ProjectStatus.DRAFT
    valid_document_count: int = 0
    prepared_document_count: int = 0
    guided_test_count: int = 0
    has_blocking_preparation_error: bool = False
    readiness_confirmed: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    description: str = ""
    current_version_id: str | None = None


@dataclass(slots=True)
class Asset:
    id: str
    workspace_id: str
    project_id: str
    original_name: str
    safe_name: str
    media_type: str
    size_bytes: int
    checksum: str
    storage_key: str
    status: AssetStatus = AssetStatus.UPLOADED
    participant_message: str | None = None
    normalized_text: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    id: str
    workspace_id: str
    project_id: str
    project_version_id: str
    asset_id: str
    source_name: str
    position: int
    text: str
    embedding: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ProjectVersion:
    id: str
    workspace_id: str
    project_id: str
    number: int
    asset_ids: tuple[str, ...]
    assistant_config: Mapping[str, str]
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "assistant_config", MappingProxyType(dict(self.assistant_config)))


@dataclass(frozen=True, slots=True)
class GuidedTest:
    id: str
    project_id: str
    project_version_id: str
    user_id: str
    question_summary: str
    cited_asset_ids: tuple[str, ...]
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class UsageEvent:
    id: str
    user_id: str
    workspace_id: str
    project_id: str
    operation: str
    provider: str
    model: str
    occurred_at: datetime
    status: str
    request_units: int
    estimated_cost: float
    correlation_id: str


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    id: str
    project_id: str
    user_id: str
    event_type: str
    occurred_at: datetime
    safe_metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "safe_metadata", MappingProxyType(dict(self.safe_metadata)))


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: str
    actor_user_id: str | None
    workspace_id: str
    project_id: str | None
    action: str
    occurred_at: datetime
    outcome: str


@dataclass(frozen=True, slots=True)
class PublishedChunk:
    asset_id: str
    source_name: str
    position: int
    text: str


@dataclass(frozen=True, slots=True)
class Publication:
    id: str
    workspace_id: str
    project_id: str
    project_version_id: str
    owner_user_id: str
    project_name: str
    created_at: datetime
    assistant_config: Mapping[str, str]
    asset_ids: tuple[str, ...]
    chunks: tuple[PublishedChunk, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "assistant_config", MappingProxyType(dict(self.assistant_config)))


@dataclass(slots=True)
class ShareLink:
    publication_id: str
    token_hash: str | None = None
    visibility: PublicationVisibility = PublicationVisibility.PRIVATE
    enabled_at: datetime | None = None
    revoked_at: datetime | None = None
