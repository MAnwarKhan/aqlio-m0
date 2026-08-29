"""Deterministic development adapters."""

from app.adapters.deterministic import (
    DeterministicDevelopmentAuth,
    DeterministicIdFactory,
    FakeClock,
    FakeEmbeddingAdapter,
    FakeGenerationAdapter,
    InMemoryM0Repository,
    InMemoryProjectRepository,
    InMemoryStorageAdapter,
    SystemClock,
    UUIDIdFactory,
)
from app.adapters.oidc_auth import StreamlitOIDCAuth
from app.adapters.openai_ai import OpenAIEmbeddingAdapter, OpenAIGenerationAdapter
from app.adapters.rate_limit import InMemoryRateLimiter
from app.adapters.sqlalchemy_repository import SQLAlchemyM0Repository
from app.adapters.storage import (
    LocalPrivateStorage,
    S3CompatiblePrivateStorage,
    StorageAdapterError,
)

__all__ = [
    "DeterministicDevelopmentAuth",
    "DeterministicIdFactory",
    "FakeClock",
    "FakeEmbeddingAdapter",
    "FakeGenerationAdapter",
    "InMemoryM0Repository",
    "InMemoryProjectRepository",
    "InMemoryRateLimiter",
    "InMemoryStorageAdapter",
    "LocalPrivateStorage",
    "OpenAIEmbeddingAdapter",
    "OpenAIGenerationAdapter",
    "S3CompatiblePrivateStorage",
    "SQLAlchemyM0Repository",
    "StorageAdapterError",
    "StreamlitOIDCAuth",
    "SystemClock",
    "UUIDIdFactory",
]
