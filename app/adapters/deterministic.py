"""Credential-free deterministic adapters for development and tests."""

import hashlib
from collections.abc import Sequence
from copy import deepcopy
from datetime import UTC, datetime
from itertools import count

from app.domain.models import Project, User
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


class FakeEmbeddingAdapter:
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vectors.append([round(byte / 255, 6) for byte in digest[:8]])
        return vectors


class FakeGenerationAdapter:
    def generate(self, request: GenerationRequest) -> GenerationResponse:
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
