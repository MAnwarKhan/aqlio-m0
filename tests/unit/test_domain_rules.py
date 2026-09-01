import pytest

from app.domain.models import Project, ProjectStatus
from app.domain.rules import InvalidTransition, assess_readiness, transition_project


def project() -> Project:
    return Project(id="project-1", workspace_id="workspace-1", owner_user_id="user-1", name="Guide")


def test_readiness_requires_every_approved_condition() -> None:
    item = project()
    assert len(assess_readiness(item).missing) == 4

    item.valid_document_count = 1
    item.prepared_document_count = 1
    item.guided_test_count = 1
    item.readiness_confirmed = True

    assert assess_readiness(item).ready


def test_blocking_preparation_error_prevents_readiness() -> None:
    item = project()
    item.valid_document_count = 1
    item.prepared_document_count = 1
    item.guided_test_count = 1
    item.readiness_confirmed = True
    item.has_blocking_preparation_error = True

    assert not assess_readiness(item).ready


def test_invalid_lifecycle_jump_is_rejected() -> None:
    item = project()

    with pytest.raises(InvalidTransition):
        transition_project(item, ProjectStatus.DEPLOYED)


def test_ready_transition_enforces_readiness() -> None:
    item = project()
    item.status = ProjectStatus.TESTED

    with pytest.raises(InvalidTransition, match="not ready"):
        transition_project(item, ProjectStatus.READY)

    item.valid_document_count = 1
    item.prepared_document_count = 1
    item.guided_test_count = 1
    item.readiness_confirmed = True
    transition_project(item, ProjectStatus.READY)

    assert item.status is ProjectStatus.READY
