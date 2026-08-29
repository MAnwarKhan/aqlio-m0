from app.adapters import FakeGenerationAdapter
from app.ports.contracts import GenerationRequest


def test_no_context_always_produces_honest_abstention() -> None:
    response = FakeGenerationAdapter().generate(GenerationRequest("Unsupported question", []))

    assert response.abstained
    assert "documents provided" in response.answer
