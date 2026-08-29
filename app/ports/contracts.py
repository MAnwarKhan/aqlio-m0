"""Protocols used by application code instead of external implementations."""

from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.models import (
    Asset,
    AuditEvent,
    DocumentChunk,
    GuidedTest,
    LifecycleEvent,
    Project,
    ProjectVersion,
    Publication,
    ShareLink,
    UsageEvent,
    User,
    Workspace,
    WorkspaceMember,
)


class AuthenticationRequired(RuntimeError):
    """Authentication boundary did not provide a valid identity."""


class ProviderCallError(RuntimeError):
    """Normalized managed-provider failure without raw provider details."""

    def __init__(
        self,
        category: str,
        *,
        provider: str,
        model: str,
        retry_count: int = 0,
        latency_ms: int = 0,
    ) -> None:
        super().__init__("We couldn't complete that request right now. Please try again.")
        self.category = category
        self.provider = provider
        self.model = model
        self.retry_count = retry_count
        self.latency_ms = latency_ms


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    document_id: str
    document_name: str
    chunk_id: str
    text: str


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    question: str
    context: Sequence[RetrievedContext]


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    provider: str
    model: str
    input_units: int = 0
    output_units: int = 0
    estimated_cost: float = 0.0
    latency_ms: int = 0
    retry_count: int = 0
    cost_is_estimated: bool = True


@dataclass(frozen=True, slots=True)
class Citation:
    document_name: str
    chunk_id: str


@dataclass(frozen=True, slots=True)
class GenerationResponse:
    answer: str
    citations: tuple[Citation, ...]
    abstained: bool = False
    usage: ProviderUsage | None = None


@dataclass(frozen=True, slots=True)
class EmbeddingResponse:
    vectors: tuple[tuple[float, ...], ...]
    usage: ProviderUsage | None = None


class AuthPort(Protocol):
    def current_user(self) -> User: ...


class ClockPort(Protocol):
    def now(self) -> datetime: ...


class IdPort(Protocol):
    def new_id(self) -> str: ...


class GenerationPort(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResponse: ...


class EmbeddingPort(Protocol):
    def embed(self, texts: Sequence[str]) -> EmbeddingResponse: ...


class ProjectRepositoryPort(Protocol):
    def save(self, project: Project) -> None: ...

    def get_for_owner(self, project_id: str, owner_user_id: str) -> Project | None: ...


class M0RepositoryPort(Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...

    def save_user(self, user: User) -> None: ...

    def get_user(self, user_id: str) -> User | None: ...

    def get_workspace_for_user(self, user_id: str) -> Workspace | None: ...

    def save_workspace(self, workspace: Workspace, member: WorkspaceMember) -> None: ...

    def is_workspace_member(self, workspace_id: str, user_id: str) -> bool: ...

    def save_project(self, project: Project) -> None: ...

    def get_project(self, project_id: str) -> Project | None: ...

    def list_projects_for_user(self, user_id: str) -> list[Project]: ...

    def save_asset(self, asset: Asset) -> None: ...

    def get_asset(self, asset_id: str) -> Asset | None: ...

    def list_assets(self, project_id: str) -> list[Asset]: ...

    def find_asset_by_checksum(self, project_id: str, checksum: str) -> Asset | None: ...

    def save_version(self, version: ProjectVersion) -> None: ...

    def get_version(self, version_id: str) -> ProjectVersion | None: ...

    def version_count(self, project_id: str) -> int: ...

    def replace_chunks(self, asset_id: str, chunks: Sequence[DocumentChunk]) -> None: ...

    def list_chunks(self, project_id: str, version_id: str) -> list[DocumentChunk]: ...

    def save_guided_test(self, test: GuidedTest) -> None: ...

    def save_usage(self, event: UsageEvent) -> None: ...

    def usage_count_for_user(self, user_id: str) -> int: ...

    def get_daily_allowance(self, user_id: str) -> int | None: ...

    def set_daily_allowance(self, user_id: str, limit: int, updated_at: datetime) -> None: ...

    def save_lifecycle(self, event: LifecycleEvent) -> None: ...

    def save_audit(self, event: AuditEvent) -> None: ...

    def save_publication(self, publication: Publication) -> None: ...

    def get_publication(self, publication_id: str) -> Publication | None: ...

    def get_publication_for_idempotency(self, key: str) -> Publication | None: ...

    def bind_publication_idempotency(self, key: str, publication_id: str) -> None: ...

    def save_share_link(self, link: ShareLink) -> None: ...

    def get_share_link(self, publication_id: str) -> ShareLink | None: ...

    def find_share_link_by_hash(self, token_hash: str) -> ShareLink | None: ...

    def list_users(self) -> list[User]: ...

    def list_all_projects(self) -> list[Project]: ...

    def list_failed_assets(self) -> list[Asset]: ...

    def list_usage_events(self) -> list[UsageEvent]: ...

    def list_share_links(self) -> list[ShareLink]: ...

    def list_lifecycle_events(self) -> list[LifecycleEvent]: ...

    def list_audit_events(self) -> list[AuditEvent]: ...


class StoragePort(Protocol):
    def put(self, *, workspace_id: str, project_id: str, content: bytes) -> str: ...

    def get(self, *, workspace_id: str, project_id: str, storage_key: str) -> bytes: ...

    def delete(self, *, workspace_id: str, project_id: str, storage_key: str) -> None: ...


class RateLimitPort(Protocol):
    def allow(self, *, subject: str, operation: str, limit: int, window_seconds: int) -> bool: ...
