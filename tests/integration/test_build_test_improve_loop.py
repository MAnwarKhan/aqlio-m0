import pytest

from app.application.errors import NotReadyError, ValidationError
from tests.helpers import build_service, prepare_project


def test_irrelevant_retrieval_abstains_and_cannot_be_confirmed() -> None:
    service = build_service()
    project = service.create_project("Company research")
    service.add_and_prepare_document(
        project.id,
        "notes.txt",
        b"Several companies increased spending during a platform expansion.",
    )

    answer = service.ask_question(project.id, "List all the companies with SPAC", guided=True)

    assert answer.abstained and not answer.citations
    assert service.get_my_project(project.id).guided_test_count == 0
    with pytest.raises(NotReadyError):
        service.publish_working_application(project.id)


def test_complete_list_request_returns_every_supported_item() -> None:
    service = build_service()
    project = service.create_project("SPAC research")
    service.add_and_prepare_document(
        project.id,
        "spacs.txt",
        (
            b"Companies with SPAC transactions are Alpha Corp, Beta Labs, and Gamma Systems. "
            b"These are the complete supported SPAC companies in this document."
        ),
    )

    answer = service.ask_question(project.id, "List all companies with SPAC")

    assert not answer.abstained
    assert all(name in answer.text for name in ("Alpha Corp", "Beta Labs", "Gamma Systems"))
    assert answer.citations


def test_runtime_separates_retrieval_from_factual_and_list_answers() -> None:
    service = build_service()
    project = service.create_project("Community center guide")
    service.add_and_prepare_document(
        project.id,
        "center.txt",
        (
            b"Registration opens on the first Monday in March.\n"
            b"Available classes:\n"
            b"- Pottery\n"
            b"- Woodworking\n"
            b"- Photography\n"
            b"The building was renovated in 2022."
        ),
    )

    factual = service.ask_question(project.id, "When does registration open?")
    listed = service.ask_question(project.id, "List all available classes.")

    assert factual.text == "Registration opens on the first Monday in March."
    assert "Pottery" not in factual.text
    assert listed.text.splitlines() == ["- Pottery", "- Woodworking", "- Photography"]
    assert "renovated" not in listed.text
    assert factual.citations and listed.citations


def test_participant_confirmation_and_feedback_control_test_success() -> None:
    service = build_service()
    project_id, _ = prepare_project(service)
    answer = service.ask_question(project_id, "When is annual leave available?", guided=True)

    assert service.get_my_project(project_id).guided_test_count == 0
    service.record_test_feedback(
        project_id, answer.correlation_id, "It missed the manager approval requirement."
    )
    project = service.get_my_project(project_id)
    assert project.guided_test_count == 0
    assert project.metadata["improvement_feedback"] == (
        "It missed the manager approval requirement."
    )

    retest = service.ask_question(project_id, "When is annual leave available?", guided=True)
    service.confirm_test_success(project_id, retest.correlation_id)
    assert service.get_my_project(project_id).guided_test_count == 1


def test_applied_improvement_persists_requires_retest_and_preserves_publication() -> None:
    service = build_service()
    project_id, _ = prepare_project(service)
    answer = service.ask_question(project_id, "When is annual leave available?", guided=True)
    service.confirm_test_success(project_id, answer.correlation_id)
    publication = service.publish_working_application(project_id)
    published_config = dict(publication.assistant_config)

    proposal = service.propose_improvement(
        project_id,
        "State approval requirements clearly.",
        response_style="detailed",
    )
    version = service.apply_improvement(
        project_id, proposal.request, response_style=proposal.response_style
    )

    assert dict(version.assistant_config) | {} == {
        **published_config,
        "response_style": "detailed",
        "response_guidance": "State approval requirements clearly.",
        "improvement_request": "State approval requirements clearly.",
    }
    assert service.get_my_project(project_id).guided_test_count == 0
    with pytest.raises(NotReadyError):
        service.publish_working_application(project_id)
    assert dict(service.repository.get_publication(publication.id).assistant_config) == (
        published_config
    )


def test_unsupported_improvement_is_explained_and_cannot_be_applied() -> None:
    service = build_service()
    project_id, _ = prepare_project(service)

    proposal = service.propose_improvement(
        project_id,
        "Add voice control and send answers to our accounting system.",
        response_style="balanced",
    )

    assert not proposal.supported
    assert "not supported" in proposal.summary
    with pytest.raises(ValidationError, match="answer-focused"):
        service.apply_improvement(
            project_id, proposal.request, response_style=proposal.response_style
        )


def test_ui_improvement_updates_specification_requires_retest_and_preserves_publication() -> None:
    service = build_service()
    project_id, _ = prepare_project(service)
    answer = service.ask_question(project_id, "When is annual leave available?", guided=True)
    service.confirm_test_success(project_id, answer.correlation_id)
    publication = service.publish_working_application(project_id)
    published_config = dict(publication.assistant_config)

    proposal = service.propose_ui_improvement(
        project_id,
        "Put the question box at the bottom and show the answer as a table.",
        title="Handbook Answers",
        instructions="Ask a question about workplace policies.",
        question_position="bottom",
        response_layout="table",
        citation_presentation="compact",
        display_density="detailed",
    )
    version = service.apply_ui_improvement(
        project_id,
        proposal.request,
        **proposal.ui_config,
    )
    specification = service.get_application_specification(project_id)

    assert proposal.supported
    assert specification.project_version_id == version.id
    assert specification.name == "Handbook Answers"
    assert specification.ui_config == {
        "title": "Handbook Answers",
        "instructions": "Ask a question about workplace policies.",
        "question_position": "bottom",
        "response_layout": "table",
        "citation_presentation": "compact",
        "display_density": "detailed",
        "improvement_request": proposal.request,
    }
    assert service.get_my_project(project_id).guided_test_count == 0
    assert dict(service.repository.get_publication(publication.id).assistant_config) == (
        published_config
    )


def test_unsupported_ui_improvement_is_rejected_honestly() -> None:
    service = build_service()
    project_id, _ = prepare_project(service)

    proposal = service.propose_ui_improvement(
        project_id,
        "Add animated video and custom JavaScript.",
        title="Handbook Assistant",
        instructions="Ask about the handbook.",
        question_position="top",
        response_layout="prose",
        citation_presentation="expanded",
        display_density="balanced",
    )

    assert not proposal.supported
    assert "not supported" in proposal.summary
    with pytest.raises(ValidationError, match="title, instructions"):
        service.apply_ui_improvement(
            project_id,
            proposal.request,
            **proposal.ui_config,
        )
