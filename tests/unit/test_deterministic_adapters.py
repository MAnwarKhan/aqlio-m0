import pytest

from app.adapters import (
    DeterministicDevelopmentAuth,
    DeterministicIdFactory,
    FakeEmbeddingAdapter,
    FakeGenerationAdapter,
    InMemoryProjectRepository,
    InMemoryStorageAdapter,
)
from app.domain.models import Project
from app.ports.contracts import GenerationRequest, RetrievedContext


def test_development_identity_is_stable() -> None:
    assert DeterministicDevelopmentAuth().current_user().id == "dev-user-0001"


def test_ids_and_embeddings_are_deterministic() -> None:
    ids = DeterministicIdFactory("project")
    assert [ids.new_id(), ids.new_id()] == ["project-0001", "project-0002"]
    adapter = FakeEmbeddingAdapter()
    assert adapter.embed(["same"]) == adapter.embed(["same"])


def test_fake_generation_cites_context_and_abstains_without_it() -> None:
    adapter = FakeGenerationAdapter()
    source = RetrievedContext("doc-1", "guide.txt", "chunk-1", "Leave is available after 30 days.")

    grounded = adapter.generate(GenerationRequest("When is leave available?", [source]))
    abstained = adapter.generate(GenerationRequest("What is the policy?", []))

    assert grounded.citations[0].document_name == "guide.txt"
    assert not grounded.abstained
    assert abstained.abstained
    assert abstained.citations == ()


def test_project_repository_enforces_owner_scope() -> None:
    repository = InMemoryProjectRepository()
    item = Project("project-1", "workspace-1", "owner-1", "Guide")
    repository.save(item)

    assert repository.get_for_owner("project-1", "owner-1") is not None
    assert repository.get_for_owner("project-1", "owner-2") is None


def test_storage_enforces_workspace_and_project_scope() -> None:
    storage = InMemoryStorageAdapter()
    key = storage.put(workspace_id="workspace-1", project_id="project-1", content=b"private")

    stored = storage.get(workspace_id="workspace-1", project_id="project-1", storage_key=key)
    assert stored == b"private"
    with pytest.raises(KeyError):
        storage.get(workspace_id="workspace-1", project_id="project-2", storage_key=key)
