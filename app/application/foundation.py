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
    InMemoryRateLimiter,
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
    RateLimitPort,
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
    rate_limiter: RateLimitPort


def build_development_foundation(settings: Settings | None = None) -> Foundation:
    resolved = settings or Settings.from_env()
    if resolved.auth_mode != "development" or resolved.ai_mode != "fake":
        raise ValueError("Phase 1 supports development authentication and fake AI only.")
    clock = FakeClock()
    return Foundation(
        settings=resolved,
        auth=DeterministicDevelopmentAuth(),
        clock=clock,
        ids=DeterministicIdFactory(),
        generation=FakeGenerationAdapter(),
        embedding=FakeEmbeddingAdapter(),
        projects=InMemoryProjectRepository(),
        state=InMemoryM0Repository(),
        storage=InMemoryStorageAdapter(),
        rate_limiter=InMemoryRateLimiter(clock),
    )
