"""Pilot/development adapter composition selected entirely by validated configuration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import boto3  # type: ignore[import-untyped]

from app.adapters import (
    DeterministicDevelopmentAuth,
    FakeEmbeddingAdapter,
    FakeGenerationAdapter,
    InMemoryM0Repository,
    InMemoryProjectRepository,
    InMemoryRateLimiter,
    InMemoryStorageAdapter,
    LocalPrivateStorage,
    S3CompatiblePrivateStorage,
    SQLAlchemyM0Repository,
    StreamlitOIDCAuth,
    SystemClock,
    UUIDIdFactory,
)
from app.application.foundation import Foundation
from app.config import Settings
from app.domain import User
from app.infrastructure.database import create_database_engine, create_session_factory
from app.ports import AuthPort, M0RepositoryPort, StoragePort


def build_runtime_foundation(
    settings: Settings,
    *,
    claims_loader: Callable[[], Mapping[str, Any]] | None = None,
) -> Foundation:
    clock = SystemClock()
    auth: AuthPort
    if settings.auth_mode == "development":
        development_user = User(
            "dev-user-0001",
            "builder@aqlio.local",
            "Aqlio Builder",
            is_admin="builder@aqlio.local" in settings.admin_emails,
        )
        auth = DeterministicDevelopmentAuth(development_user)
    elif claims_loader is not None:
        auth = StreamlitOIDCAuth(
            claims_loader,
            provider=settings.oidc_provider or "google",
            admin_emails=settings.admin_emails,
        )
    else:
        raise ValueError("Authenticated pilot mode requires an identity claims loader.")

    state: M0RepositoryPort
    if settings.persistence_mode == "sqlalchemy":
        if not settings.database_url:
            raise ValueError("Durable persistence requires DATABASE_URL.")
        engine = create_database_engine(settings.database_url)
        state = SQLAlchemyM0Repository(create_session_factory(engine))
    else:
        state = InMemoryM0Repository()

    storage: StoragePort
    if settings.storage_mode == "local":
        storage = LocalPrivateStorage(Path(settings.local_storage_path))
    elif settings.storage_mode == "s3":
        client = boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint,
            region_name=settings.object_storage_region,
            aws_access_key_id=settings.object_storage_access_key_id,
            aws_secret_access_key=settings.object_storage_secret_access_key,
        )
        storage = S3CompatiblePrivateStorage(client, settings.object_storage_bucket or "")
    else:
        storage = InMemoryStorageAdapter()

    return Foundation(
        settings=settings,
        auth=auth,
        clock=clock,
        ids=UUIDIdFactory(),
        generation=FakeGenerationAdapter(),
        embedding=FakeEmbeddingAdapter(),
        projects=InMemoryProjectRepository(),
        state=state,
        storage=storage,
        rate_limiter=InMemoryRateLimiter(clock),
    )
