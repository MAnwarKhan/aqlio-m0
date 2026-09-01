import pytest

from app.adapters import FakeGenerationAdapter
from app.application.errors import (
    AllowanceExceeded,
    AuthorizationError,
    NotReadyError,
    ValidationError,
)
from app.application.journey import next_step, project_status
from app.domain import ProjectStatus, User
from app.ports import ProviderCallError
from tests.helpers import build_service, fixture_bytes, prepare_project


def test_optional_evaluation_and_independent_resumable_ideas():
    service = build_service()
    one = service.create_idea("Help students understand admissions documents")
    two = service.create_idea("Help students understand admissions documents")
    assert one.id != two.id
    assert project_status(one) == "Idea"
    fields = {
        key: "A short useful description"
        for key in ("problem", "users", "outcome", "ai_role", "information")
    }
    service.update_definition(one.id, fields)
    service.define_solution(one.id)
    assert next_step(service.get_my_project(one.id)) == "build"
    assert project_status(service.get_my_project(two.id)) == "Idea"
    assert service.repository.list_usage_events() == []
    evaluation = service.evaluate_idea(one.id)
    assert all(
        label in evaluation
        for label in (
            "Problem:",
            "Users:",
            "Impact:",
            "AI Fit:",
            "Feasibility:",
            "Differentiation:",
        )
    )
    assert service.repository.list_usage_events()[-1].operation == "EVALUATE_IDEA"
    service.update_definition(one.id, {"idea": "A revised idea"})
    assert "idea_evaluation" not in service.get_my_project(one.id).metadata


def test_evaluation_allowance_failure_and_authorization():
    service = build_service(allowance=1)
    project = service.create_idea("Explain policies")
    service.evaluate_idea(project.id)
    with pytest.raises(AllowanceExceeded):
        service.evaluate_idea(project.id)
    assert service.generation.call_count == 1
    outsider = build_service(
        user=User("other", "other@example.com", "Other"), repository=service.repository
    )
    for action in (
        lambda: outsider.evaluate_idea(project.id),
        lambda: outsider.update_definition(project.id, {"idea": "stolen"}),
        lambda: outsider.improve_application(project.id, "short", answer_length="short"),
        lambda: outsider.run_application(project.id, "Question"),
    ):
        with pytest.raises(AuthorizationError):
            action()

    class Failing(FakeGenerationAdapter):
        def generate(self, request):
            raise ProviderCallError("TIMEOUT", provider="fake", model="test")

    failing = build_service(generation=Failing())
    idea = failing.create_idea("Help people")
    with pytest.raises(ProviderCallError):
        failing.evaluate_idea(idea.id)
    assert failing.repository.list_usage_events()[-1].status == "FAILED"
    assert failing.get_my_project(idea.id).metadata["idea"] == "Help people"


def test_improve_retest_run_and_publish_preserves_previous_publication():
    service = build_service()
    project_id, _ = prepare_project(service)
    question = "When is annual leave available?"
    with pytest.raises(NotReadyError):
        service.run_application(project_id, question)
    with pytest.raises(NotReadyError):
        service.publish_working_application(project_id)
    service.ask_question(project_id, question, guided=True)
    service.run_application(project_id, question)
    assert project_status(service.get_my_project(project_id)) == "Working"
    publication = service.publish_working_application(project_id)
    receipt = service.enable_link_sharing(publication.id)
    original = service.ask_shared(receipt.token, question)
    old_version = service.get_my_project(project_id).current_version_id
    version = service.improve_application(
        project_id, "The answers are too long", answer_length="short"
    )
    assert version.id != old_version
    project = service.get_my_project(project_id)
    assert project.status == ProjectStatus.PREPARED
    assert not project.readiness_confirmed and project.guided_test_count == 0
    assert "run_version_id" not in project.metadata
    with pytest.raises(NotReadyError):
        service.publish_working_application(project_id)
    short = service.ask_question(project_id, question, guided=True)
    assert len(short.text) < len(original.text)
    assert short.citations
    service.run_application(project_id, question)
    newer = service.publish_working_application(project_id)
    assert newer.id != publication.id
    assert service.repository.get_publication(publication.id) == publication
    assert service.ask_shared(receipt.token, question).text == original.text
    assert service.publish_working_application(project_id).id == newer.id


def test_unsupported_improvements_do_not_create_versions():
    service = build_service()
    project_id, _ = prepare_project(service)
    before = service.get_my_project(project_id).current_version_id
    with pytest.raises(ValidationError):
        service.improve_application(project_id, "Build an agent", answer_length="agent")
    with pytest.raises(ValidationError):
        service.improve_application(project_id, "Summarize everything", answer_length="standard")
    assert service.get_my_project(project_id).current_version_id == before


def test_new_documents_require_current_version_test_and_keep_length():
    service = build_service()
    project_id, _ = prepare_project(service)
    service.improve_application(project_id, "Shorter", answer_length="short")
    service.ask_question(project_id, "When is annual leave available?", guided=True)
    service.run_application(project_id, "When is annual leave available?")
    service.add_and_prepare_document(project_id, "another.txt", b"More annual leave information.")
    project = service.get_my_project(project_id)
    assert project.guided_test_count == 0
    assert (
        service.repository.get_version(project.current_version_id).assistant_config["answer_length"]
        == "short"
    )


def test_one_successful_preparation_does_not_hide_another_failure():
    service = build_service()
    project = service.create_project("Mixed documents")
    bad = service.upload_document(project.id, "empty.txt", b"   ")
    from app.application.errors import PreparationError

    with pytest.raises(PreparationError):
        service.prepare_document(project.id, bad.id)
    service.add_and_prepare_document(
        project.id, "handbook.txt", fixture_bytes("employee_handbook.txt")
    )
    assert service.get_my_project(project.id).has_blocking_preparation_error


def test_failed_rebuild_preserves_current_draft_chunks():
    from app.adapters import FakeEmbeddingAdapter
    from app.application.errors import PreparationError

    class FailSecond(FakeEmbeddingAdapter):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def embed(self, texts):
            self.calls += 1
            if self.calls == 2:
                raise ProviderCallError("TIMEOUT", provider="fake", model="test")
            return super().embed(texts)

    service = build_service()
    project_id, _ = prepare_project(service)
    before = service.get_my_project(project_id).current_version_id
    chunks = service.repository.list_chunks(project_id, before)
    service.embedding = FailSecond()
    with pytest.raises(PreparationError):
        service.add_and_prepare_document(project_id, "another.txt", b"New policy information.")
    assert service.get_my_project(project_id).current_version_id == before
    assert service.repository.list_chunks(project_id, before) == chunks
    assert service.repository.list_usage_events()[-1].status == "FAILED"


def test_legacy_publications_remain_discoverable():
    from tests.helpers import deploy_project

    service = build_service()
    project_id, publication_id = deploy_project(service)
    assert "publication_id" not in service.get_my_project(project_id).metadata
    assert service.latest_publication(project_id).id == publication_id
