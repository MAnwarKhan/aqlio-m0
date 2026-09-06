from dataclasses import FrozenInstanceError

import pytest

from app.application.errors import AuthorizationError, NotReadyError
from app.domain import User, VersionApprovalState
from tests.helpers import build_service, prepare_project


def confirm_current_version(service, project_id: str) -> None:
    answer = service.ask_question(project_id, "When is annual leave available?", guided=True)
    service.confirm_test_success(project_id, answer.correlation_id)


def test_approval_requires_confirmed_test_of_exact_working_version() -> None:
    service = build_service()
    project_id, _ = prepare_project(service)

    with pytest.raises(NotReadyError, match="Test the current Working Version"):
        service.approve_working_version(project_id)

    confirm_current_version(service, project_id)
    service.apply_improvement(project_id, "Use clearer wording", response_style="balanced")

    with pytest.raises(NotReadyError, match="Test the current Working Version"):
        service.approve_working_version(project_id)


def test_approval_snapshots_specification_and_later_changes_do_not_mutate_it() -> None:
    service = build_service()
    project_id, _ = prepare_project(service)
    service.apply_ui_improvement(
        project_id,
        "Show the answer as a table with compact citations.",
        title="Policy Answers",
        instructions="Ask about workplace policies.",
        question_position="top",
        response_layout="table",
        citation_presentation="compact",
        display_density="balanced",
    )
    confirm_current_version(service, project_id)
    approved = service.approve_working_version(project_id)
    approved_version_id = approved.specification.project_version_id
    approved_ui = dict(approved.specification.ui_config)

    assert approved.specification.approval_state == VersionApprovalState.APPROVED
    assert approved.specification.name == "Policy Answers"
    with pytest.raises(TypeError):
        approved.specification.ui_config["title"] = "Changed"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        approved.owner_user_id = "other"  # type: ignore[misc]

    service.apply_improvement(project_id, "Give more detailed answers", response_style="detailed")
    persisted = service.get_approved_version(approved.id)
    assert persisted.specification.project_version_id == approved_version_id
    assert dict(persisted.specification.ui_config) == approved_ui
    with pytest.raises(NotReadyError):
        service.approve_working_version(project_id)

    confirm_current_version(service, project_id)
    newer = service.approve_working_version(project_id)
    assert newer.id != approved.id
    assert newer.specification.project_version_id != approved_version_id


def test_approval_enforces_project_authorization_and_publication_is_independent() -> None:
    owner = build_service()
    project_id, _ = prepare_project(owner)
    confirm_current_version(owner, project_id)
    publication = owner.publish_working_application(project_id)
    approved = owner.approve_working_version(project_id)
    publication_snapshot = owner.repository.get_publication(publication.id)

    other = build_service(
        user=User("other-user", "other@example.com", "Other"),
        repository=owner.repository,
        storage=owner.storage,  # type: ignore[arg-type]
    )
    with pytest.raises(AuthorizationError):
        other.approve_working_version(project_id)
    with pytest.raises(AuthorizationError):
        other.get_approved_version(approved.id)

    owner.apply_ui_improvement(
        project_id,
        "Move the question box to the bottom.",
        title="Updated Working Version",
        instructions="Ask a question.",
        question_position="bottom",
        response_layout="prose",
        citation_presentation="expanded",
        display_density="balanced",
    )
    assert owner.repository.get_publication(publication.id) == publication_snapshot
    assert owner.get_approved_version(approved.id) == approved
