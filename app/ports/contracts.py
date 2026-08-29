"""Protocols used by application code instead of external implementations."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.models import Project, User


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
class Citation:
    document_name: str
    chunk_id: str


@dataclass(frozen=True, slots=True)
class GenerationResponse:
    answer: str
    citations: tuple[Citation, ...]
    abstained: bool = False


class AuthPort(Protocol):
    def current_user(self) -> User: ...


class ClockPort(Protocol):
    def now(self) -> datetime: ...


class IdPort(Protocol):
    def new_id(self) -> str: ...


class GenerationPort(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResponse: ...


class EmbeddingPort(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class ProjectRepositoryPort(Protocol):
    def save(self, project: Project) -> None: ...

    def get_for_owner(self, project_id: str, owner_user_id: str) -> Project | None: ...


class StoragePort(Protocol):
    def put(self, *, workspace_id: str, project_id: str, content: bytes) -> str: ...

    def get(self, *, workspace_id: str, project_id: str, storage_key: str) -> bytes: ...

    def delete(self, *, workspace_id: str, project_id: str, storage_key: str) -> None: ...
