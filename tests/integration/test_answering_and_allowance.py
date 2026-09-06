import pytest

from app.adapters import FakeGenerationAdapter
from app.application.errors import AllowanceExceeded
from tests.helpers import build_service, prepare_project


def test_grounded_answer_citation_abstention_and_usage() -> None:
    service = build_service()
    project_id, _asset_id = prepare_project(service)

    grounded = service.ask_question(project_id, "When is annual leave available?", guided=True)
    unsupported = service.ask_question(project_id, "What is the cafeteria menu?", guided=False)

    assert not grounded.abstained
    assert grounded.citations[0].document_name == "employee_handbook.txt"
    assert unsupported.abstained
    assert unsupported.citations == ()
    assert len(service.repository.usage_events) == 2
    assert all(event.estimated_cost == 0 for event in service.repository.usage_events)
    assert service.get_my_project(project_id).guided_test_count == 0
    service.confirm_test_success(project_id, grounded.correlation_id)
    assert service.get_my_project(project_id).guided_test_count == 1


def test_allowance_is_enforced_before_generation() -> None:
    generation = FakeGenerationAdapter()
    service = build_service(generation=generation, allowance=1)
    project_id, _asset_id = prepare_project(service)
    service.ask_question(project_id, "When is annual leave available?")

    with pytest.raises(AllowanceExceeded, match="usage allowance"):
        service.ask_question(project_id, "How many leave days are available?")

    assert generation.call_count == 1
    assert service.repository.usage_events[-1].status == "REJECTED"
