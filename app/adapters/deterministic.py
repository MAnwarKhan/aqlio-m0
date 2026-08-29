"""Credential-free deterministic adapters for development and tests."""

import hashlib
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from itertools import count
from uuid import uuid4

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
from app.ports.contracts import Citation, GenerationRequest, GenerationResponse


class DeterministicDevelopmentAuth:
    def __init__(self, user: User | None = None) -> None:
        self._user = user or User(
            id="dev-user-0001",
            email="builder@aqlio.local",
            display_name="Aqlio Builder",
        )

    def current_user(self) -> User:
        return self._user


class FakeClock:
    def __init__(self, value: datetime | None = None) -> None:
        self._value = value or datetime(2026, 8, 29, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._value


class DeterministicIdFactory:
    def __init__(self, prefix: str = "id") -> None:
        self._prefix = prefix
        self._counter = count(1)

    def new_id(self) -> str:
        return f"{self._prefix}-{next(self._counter):04d}"


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class UUIDIdFactory:
    def new_id(self) -> str:
        return str(uuid4())


class FakeEmbeddingAdapter:
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vectors.append([round(byte / 255, 6) for byte in digest[:8]])
        return vectors


class FakeGenerationAdapter:
    def __init__(self) -> None:
        self.call_count = 0

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        self.call_count += 1
        if not request.context:
            return GenerationResponse(
                answer="I couldn't establish that from the documents provided.",
                citations=(),
                abstained=True,
            )
        source = request.context[0]
        excerpt = " ".join(source.text.split())[:240]
        return GenerationResponse(
            answer=f"Based on {source.document_name}: {excerpt}",
            citations=(Citation(source.document_name, source.chunk_id),),
        )


class InMemoryProjectRepository:
    def __init__(self) -> None:
        self._projects: dict[str, Project] = {}

    def save(self, project: Project) -> None:
        self._projects[project.id] = deepcopy(project)

    def get_for_owner(self, project_id: str, owner_user_id: str) -> Project | None:
        project = self._projects.get(project_id)
        if project is None or project.owner_user_id != owner_user_id:
            return None
        return deepcopy(project)


class InMemoryStorageAdapter:
    def __init__(self, ids: DeterministicIdFactory | None = None) -> None:
        self._ids = ids or DeterministicIdFactory("asset")
        self._objects: dict[tuple[str, str, str], bytes] = {}

    def put(self, *, workspace_id: str, project_id: str, content: bytes) -> str:
        storage_key = self._ids.new_id()
        self._objects[(workspace_id, project_id, storage_key)] = bytes(content)
        return storage_key

    def get(self, *, workspace_id: str, project_id: str, storage_key: str) -> bytes:
        return self._objects[(workspace_id, project_id, storage_key)]

    def delete(self, *, workspace_id: str, project_id: str, storage_key: str) -> None:
        del self._objects[(workspace_id, project_id, storage_key)]


class InMemoryM0Repository:
    """Authorization-neutral state store; application services enforce access."""

    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.workspaces: dict[str, Workspace] = {}
        self.members: dict[tuple[str, str], WorkspaceMember] = {}
        self.projects: dict[str, Project] = {}
        self.assets: dict[str, Asset] = {}
        self.versions: dict[str, ProjectVersion] = {}
        self.chunks: dict[str, DocumentChunk] = {}
        self.guided_tests: list[GuidedTest] = []
        self.usage_events: list[UsageEvent] = []
        self.lifecycle_events: list[LifecycleEvent] = []
        self.audit_events: list[AuditEvent] = []
        self.publications: dict[str, Publication] = {}
        self.publication_commands: dict[str, str] = {}
        self.share_links: dict[str, ShareLink] = {}
        self.allowances: dict[str, int] = {}

    @contextmanager
    def transaction(self) -> Iterator[None]:
        snapshot = {
            key: value.copy() if isinstance(value, dict | list) else value
            for key, value in self.__dict__.items()
        }
        try:
            yield
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(snapshot)
            raise

    def save_user(self, user: User) -> None:
        existing = self.users.get(user.id)
        if existing and not existing.active:
            user = User(
                user.id,
                user.email,
                user.display_name,
                active=False,
                is_admin=existing.is_admin,
                identity_provider=user.identity_provider,
                identity_subject=user.identity_subject,
            )
        self.users[user.id] = deepcopy(user)

    def get_user(self, user_id: str) -> User | None:
        user = self.users.get(user_id)
        return deepcopy(user) if user else None

    def get_workspace_for_user(self, user_id: str) -> Workspace | None:
        for (workspace_id, member_user_id), _member in self.members.items():
            if member_user_id == user_id:
                return deepcopy(self.workspaces[workspace_id])
        return None

    def save_workspace(self, workspace: Workspace, member: WorkspaceMember) -> None:
        self.workspaces[workspace.id] = deepcopy(workspace)
        self.members[(member.workspace_id, member.user_id)] = deepcopy(member)

    def is_workspace_member(self, workspace_id: str, user_id: str) -> bool:
        return (workspace_id, user_id) in self.members

    def save_project(self, project: Project) -> None:
        self.projects[project.id] = deepcopy(project)

    def get_project(self, project_id: str) -> Project | None:
        project = self.projects.get(project_id)
        return deepcopy(project) if project else None

    def list_projects_for_user(self, user_id: str) -> list[Project]:
        return [
            deepcopy(project)
            for project in self.projects.values()
            if project.owner_user_id == user_id
        ]

    def save_asset(self, asset: Asset) -> None:
        self.assets[asset.id] = deepcopy(asset)

    def get_asset(self, asset_id: str) -> Asset | None:
        asset = self.assets.get(asset_id)
        return deepcopy(asset) if asset else None

    def list_assets(self, project_id: str) -> list[Asset]:
        return [deepcopy(asset) for asset in self.assets.values() if asset.project_id == project_id]

    def find_asset_by_checksum(self, project_id: str, checksum: str) -> Asset | None:
        for asset in self.assets.values():
            if asset.project_id == project_id and asset.checksum == checksum:
                return deepcopy(asset)
        return None

    def save_version(self, version: ProjectVersion) -> None:
        self.versions[version.id] = version

    def get_version(self, version_id: str) -> ProjectVersion | None:
        return self.versions.get(version_id)

    def version_count(self, project_id: str) -> int:
        return sum(version.project_id == project_id for version in self.versions.values())

    def replace_chunks(self, asset_id: str, chunks: Sequence[DocumentChunk]) -> None:
        self.chunks = {
            chunk_id: chunk for chunk_id, chunk in self.chunks.items() if chunk.asset_id != asset_id
        }
        self.chunks.update({chunk.id: chunk for chunk in chunks})

    def list_chunks(self, project_id: str, version_id: str) -> list[DocumentChunk]:
        return [
            chunk
            for chunk in self.chunks.values()
            if chunk.project_id == project_id and chunk.project_version_id == version_id
        ]

    def save_guided_test(self, test: GuidedTest) -> None:
        self.guided_tests.append(test)

    def save_usage(self, event: UsageEvent) -> None:
        self.usage_events.append(event)

    def usage_count_for_user(self, user_id: str) -> int:
        return sum(
            event.user_id == user_id and event.status == "SUCCEEDED" for event in self.usage_events
        )

    def get_daily_allowance(self, user_id: str) -> int | None:
        return self.allowances.get(user_id)

    def set_daily_allowance(self, user_id: str, limit: int, updated_at: datetime) -> None:
        del updated_at
        self.allowances[user_id] = limit

    def save_lifecycle(self, event: LifecycleEvent) -> None:
        self.lifecycle_events.append(event)

    def save_audit(self, event: AuditEvent) -> None:
        self.audit_events.append(event)

    def save_publication(self, publication: Publication) -> None:
        self.publications[publication.id] = publication

    def get_publication(self, publication_id: str) -> Publication | None:
        return self.publications.get(publication_id)

    def get_publication_for_idempotency(self, key: str) -> Publication | None:
        publication_id = self.publication_commands.get(key)
        return self.publications.get(publication_id) if publication_id else None

    def bind_publication_idempotency(self, key: str, publication_id: str) -> None:
        self.publication_commands[key] = publication_id

    def save_share_link(self, link: ShareLink) -> None:
        self.share_links[link.publication_id] = deepcopy(link)

    def get_share_link(self, publication_id: str) -> ShareLink | None:
        link = self.share_links.get(publication_id)
        return deepcopy(link) if link else None

    def find_share_link_by_hash(self, token_hash: str) -> ShareLink | None:
        for link in self.share_links.values():
            if link.token_hash == token_hash:
                return deepcopy(link)
        return None

    def list_users(self) -> list[User]:
        return [deepcopy(user) for user in self.users.values()]

    def list_all_projects(self) -> list[Project]:
        return [deepcopy(project) for project in self.projects.values()]

    def list_failed_assets(self) -> list[Asset]:
        return [deepcopy(asset) for asset in self.assets.values() if asset.status.value == "FAILED"]

    def list_usage_events(self) -> list[UsageEvent]:
        return list(self.usage_events)

    def list_share_links(self) -> list[ShareLink]:
        return [deepcopy(link) for link in self.share_links.values()]

    def list_lifecycle_events(self) -> list[LifecycleEvent]:
        return list(self.lifecycle_events)

    def list_audit_events(self) -> list[AuditEvent]:
        return list(self.audit_events)
