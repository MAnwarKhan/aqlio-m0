from __future__ import annotations

from dataclasses import replace

import pytest

from app.application.errors import (
    AllowanceExceeded,
    AuthorizationError,
    NotReadyError,
)
from app.domain import User
from app.ports import EmbeddingResponse, ProviderCallError, ProviderUsage
from app.ports.contracts import Citation, GenerationRequest, GenerationResponse
from tests.helpers import build_service, fixture_bytes, prepare_project


class GenerationSpy:
    def __init__(self) -> None:
        self.call_count = 0

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        self.call_count += 1
        context = request.context[0]
        return GenerationResponse(
            "Grounded answer",
            (Citation(context.document_name, context.chunk_id),),
            usage=ProviderUsage("openai", "configured", 10, 3, 0.001, 25),
        )


class EmbeddingSpy:
    def __init__(self) -> None:
        self.call_count = 0

    def embed(self, texts: list[str]) -> EmbeddingResponse:
        self.call_count += 1
        return EmbeddingResponse(tuple((0.5, 0.5) for _text in texts))


def test_managed_generation_is_never_called_before_authorization_readiness_or_allowance() -> None:
    spy = GenerationSpy()
    owner = User("owner", "owner@example.com", "Owner")
    service = build_service(user=owner, generation=spy, allowance=1)
    service.settings = replace(service.settings, ai_mode="managed")
    project = service.create_project("Controls")

    with pytest.raises(NotReadyError):
        service.ask_question(project.id, "Question")
    assert spy.call_count == 0

    project_id, _asset_id = prepare_project(service)
    service.ask_question(project_id, "When is annual leave available?")
    with pytest.raises(AllowanceExceeded):
        service.ask_question(project_id, "How many leave days are available?")
    assert spy.call_count == 1

    outsider = build_service(
        user=User("outsider", "outsider@example.com", "Outsider"),
        repository=service.repository,
        storage=service.storage,
        generation=spy,
    )
    outsider.settings = replace(outsider.settings, ai_mode="managed")
    with pytest.raises(AuthorizationError):
        outsider.ask_question(project_id, "Question")
    assert spy.call_count == 1


def test_managed_embedding_is_allowance_gated_before_call() -> None:
    service = build_service(allowance=1)
    project_id, _asset_id = prepare_project(service)
    service.ask_question(project_id, "When is annual leave available?")
    spy = EmbeddingSpy()
    service.embedding = spy
    service.settings = replace(service.settings, ai_mode="managed")
    asset = service.upload_document(
        project_id, "benefits_guide.txt", fixture_bytes("benefits_guide.txt")
    )

    with pytest.raises(AllowanceExceeded):
        service.prepare_document(project_id, asset.id)

    assert spy.call_count == 0
    assert service.repository.usage_events[-1].status == "REJECTED"


def test_normalized_provider_failure_is_recorded_without_raw_error() -> None:
    class FailingGeneration:
        def generate(self, request: GenerationRequest) -> GenerationResponse:
            del request
            raise ProviderCallError(
                "UNAVAILABLE",
                provider="openai",
                model="configured",
                retry_count=2,
                latency_ms=75,
            )

    service = build_service(generation=FailingGeneration())
    service.settings = replace(service.settings, ai_mode="managed")
    project_id, _asset_id = prepare_project(service)

    with pytest.raises(ProviderCallError, match="couldn't complete"):
        service.ask_question(project_id, "When is annual leave available?")

    event = service.repository.usage_events[-1]
    assert event.status == "FAILED"
    assert event.error_category == "UNAVAILABLE"
    assert event.retry_count == 2
    assert event.latency_ms == 75
