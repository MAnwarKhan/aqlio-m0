"""Composition root for the deterministic Phase 1 foundation."""

from dataclasses import dataclass

from app.adapters import (
    DeterministicDevelopmentAuth,
    DeterministicIdFactory,
    FakeClock,
    FakeEmbeddingAdapter,
    FakeGenerationAdapter,
    InMemoryM0Repository,
    InMemoryProjectRepository,
    InMemoryStorageAdapter,
)
from app.config import Settings
from app.ports import (
    AuthPort,
    ClockPort,
    EmbeddingPort,
    GenerationPort,
    IdPort,
    M0RepositoryPort,
    ProjectRepositoryPort,
    StoragePort,
)


@dataclass(frozen=True, slots=True)
class Foundation:
    settings: Settings
    auth: AuthPort
    clock: ClockPort
    ids: IdPort
    generation: GenerationPort
    embedding: EmbeddingPort
    projects: ProjectRepositoryPort
    state: M0RepositoryPort
    storage: StoragePort


def build_development_foundation(settings: Settings | None = None) -> Foundation:
    resolved = settings or Settings.from_env()
    if resolved.auth_mode != "development" or resolved.ai_mode != "fake":
        raise ValueError("Phase 1 supports development authentication and fake AI only.")
    return Foundation(
        settings=resolved,
        auth=DeterministicDevelopmentAuth(),
        clock=FakeClock(),
        ids=DeterministicIdFactory(),
        generation=FakeGenerationAdapter(),
        embedding=FakeEmbeddingAdapter(),
        projects=InMemoryProjectRepository(),
        state=InMemoryM0Repository(),
        storage=InMemoryStorageAdapter(),
    )
