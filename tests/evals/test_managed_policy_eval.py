from dataclasses import replace

import pytest

from app.application.errors import AllowanceExceeded
from app.ports import ProviderUsage
from app.ports.contracts import Citation, GenerationRequest, GenerationResponse
from tests.helpers import build_service, prepare_project


class CostedGenerationSpy:
    def __init__(self) -> None:
        self.call_count = 0

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        self.call_count += 1
        context = request.context[0]
        return GenerationResponse(
            "Grounded answer",
            (Citation(context.document_name, context.chunk_id),),
            usage=ProviderUsage(
                "openai",
                "configured-model",
                input_units=12,
                output_units=4,
                estimated_cost=0.002,
                latency_ms=30,
                retry_count=1,
            ),
        )


def test_managed_allowance_and_usage_metadata_have_explicit_thresholds() -> None:
    generation = CostedGenerationSpy()
    service = build_service(generation=generation, allowance=1)
    project_id, _asset_id = prepare_project(service)
    service.settings = replace(service.settings, ai_mode="managed")

    answer = service.ask_question(project_id, "When is annual leave available?")
    with pytest.raises(AllowanceExceeded):
        service.ask_question(project_id, "How many leave days are available?")

    usage = service.repository.usage_events[0]
    assert generation.call_count == 1
    assert answer.citations[0].document_name == "employee_handbook.txt"
    assert usage.request_units == 12
    assert usage.output_units == 4
    assert usage.estimated_cost == 0.002
    assert usage.retry_count == 1
