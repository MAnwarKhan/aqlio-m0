from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.adapters import (
    DeterministicDevelopmentAuth,
    DeterministicIdFactory,
    FakeClock,
    FakeEmbeddingAdapter,
    FakeGenerationAdapter,
    InMemoryM0Repository,
    InMemoryStorageAdapter,
)
from app.application import M0Service
from app.config import Settings
from app.domain import User

FIXTURES = Path(__file__).parent.parent / "fixtures"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def build_service(
    *,
    user: User | None = None,
    repository: InMemoryM0Repository | None = None,
    storage: InMemoryStorageAdapter | None = None,
    ids: DeterministicIdFactory | None = None,
    generation: FakeGenerationAdapter | None = None,
    allowance: int = 25,
) -> M0Service:
    settings = replace(Settings.from_env(), daily_ai_request_allowance=allowance)
    return M0Service(
        settings=settings,
        auth=DeterministicDevelopmentAuth(user),
        clock=FakeClock(),
        ids=ids or DeterministicIdFactory(),
        generation=generation or FakeGenerationAdapter(),
        embedding=FakeEmbeddingAdapter(),
        repository=repository or InMemoryM0Repository(),
        storage=storage or InMemoryStorageAdapter(),
    )


def prepare_project(service: M0Service, name: str = "Handbook Assistant") -> tuple[str, str]:
    project = service.create_project(name)
    asset = service.upload_document(
        project.id,
        "employee_handbook.txt",
        fixture_bytes("employee_handbook.txt"),
    )
    service.prepare_document(project.id, asset.id)
    return project.id, asset.id


def deploy_project(service: M0Service) -> tuple[str, str]:
    project_id, _asset_id = prepare_project(service)
    answer = service.ask_question(project_id, "When is annual leave available?", guided=True)
    service.confirm_test_success(project_id, answer.correlation_id)
    service.confirm_readiness(project_id)
    publication = service.deploy(project_id, idempotency_key=f"deploy-{project_id}")
    return project_id, publication.id
