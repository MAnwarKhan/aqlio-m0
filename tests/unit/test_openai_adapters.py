from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.adapters import OpenAIEmbeddingAdapter, OpenAIGenerationAdapter
from app.ports import ProviderCallError
from app.ports.contracts import GenerationRequest, RetrievedContext


class Responses:
    def __init__(self, values: list[object]) -> None:
        self.values = values
        self.calls = 0
        self.kwargs: dict[str, object] = {}

    def create(self, **kwargs: object) -> object:
        self.calls += 1
        self.kwargs = kwargs
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class Embeddings(Responses):
    pass


def generation_client(*values: object) -> SimpleNamespace:
    return SimpleNamespace(responses=Responses(list(values)))


def test_generation_accepts_only_retrieved_citations_and_records_usage() -> None:
    response = SimpleNamespace(
        output_text=(
            '{"answer":"Leave begins after 90 days.",'
            '"cited_chunk_ids":["chunk-1"],"abstained":false}'
        ),
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )
    client = generation_client(response)
    adapter = OpenAIGenerationAdapter(
        api_key="unused",
        model="configured-model",
        timeout_seconds=5,
        max_retries=0,
        input_cost_per_million=2.0,
        output_cost_per_million=4.0,
        client=client,
        monotonic=lambda: 1.0,
    )

    result = adapter.generate(
        GenerationRequest(
            "When does leave begin?",
            [RetrievedContext("asset-1", "handbook.txt", "chunk-1", "After 90 days.")],
        )
    )

    assert result.citations[0].chunk_id == "chunk-1"
    assert result.usage is not None and result.usage.input_units == 100
    assert result.usage.output_units == 20
    assert result.usage.estimated_cost == pytest.approx(0.00028)
    assert client.responses.kwargs["store"] is False
    assert client.responses.kwargs["timeout"] == 5


def test_generation_rejects_fabricated_citation() -> None:
    response = SimpleNamespace(
        output_text='{"answer":"Invented.","cited_chunk_ids":["other-project"],"abstained":false}',
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
    )
    adapter = OpenAIGenerationAdapter(
        api_key="unused",
        model="configured-model",
        timeout_seconds=5,
        max_retries=0,
        client=generation_client(response),
        monotonic=lambda: 1.0,
    )

    with pytest.raises(ProviderCallError) as error:
        adapter.generate(
            GenerationRequest(
                "Question", [RetrievedContext("asset", "safe.txt", "safe-chunk", "Evidence")]
            )
        )
    assert error.value.category == "INVALID_RESPONSE"


def test_timeout_retries_are_bounded_and_normalized() -> None:
    class APITimeoutError(Exception):
        pass

    client = generation_client(APITimeoutError(), APITimeoutError(), APITimeoutError())
    adapter = OpenAIGenerationAdapter(
        api_key="unused",
        model="configured-model",
        timeout_seconds=2,
        max_retries=2,
        client=client,
        sleeper=lambda _seconds: None,
        monotonic=lambda: 1.0,
    )

    with pytest.raises(ProviderCallError) as error:
        adapter.generate(
            GenerationRequest(
                "Question", [RetrievedContext("asset", "source.txt", "chunk", "Evidence")]
            )
        )
    assert error.value.category == "TIMEOUT"
    assert error.value.retry_count == 2
    assert client.responses.calls == 3


def test_embedding_returns_neutral_vectors_and_usage() -> None:
    response = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.25, 0.75])],
        usage=SimpleNamespace(total_tokens=50),
    )
    client = SimpleNamespace(embeddings=Embeddings([response]))
    adapter = OpenAIEmbeddingAdapter(
        api_key="unused",
        model="embedding-model",
        timeout_seconds=3,
        max_retries=0,
        input_cost_per_million=1.0,
        client=client,
        monotonic=lambda: 1.0,
    )

    result = adapter.embed(["document text"])

    assert result.vectors == ((0.25, 0.75),)
    assert result.usage is not None and result.usage.estimated_cost == pytest.approx(0.00005)


@pytest.mark.parametrize(
    ("status_code", "code", "category"),
    [
        (429, "rate_limit", "RATE_LIMITED"),
        (429, "insufficient_quota", "QUOTA_EXCEEDED"),
        (401, "", "AUTHENTICATION_ERROR"),
        (400, "", "INVALID_REQUEST"),
        (503, "", "UNAVAILABLE"),
    ],
)
def test_provider_http_errors_are_normalized(status_code: int, code: str, category: str) -> None:
    error = RuntimeError("raw provider detail")
    error.status_code = status_code  # type: ignore[attr-defined]
    error.code = code  # type: ignore[attr-defined]
    adapter = OpenAIGenerationAdapter(
        api_key="unused",
        model="configured-model",
        timeout_seconds=2,
        max_retries=0,
        client=generation_client(error),
        monotonic=lambda: 1.0,
    )

    with pytest.raises(ProviderCallError) as normalized:
        adapter.generate(
            GenerationRequest(
                "Question", [RetrievedContext("asset", "source.txt", "chunk", "Evidence")]
            )
        )

    assert normalized.value.category == category
    assert "raw provider detail" not in str(normalized.value)
