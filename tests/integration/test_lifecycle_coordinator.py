from dataclasses import replace

import pytest

from app.application.eligibility_advisor import AdvisorInput
from app.application.errors import ValidationError
from app.domain import ApplicationType
from tests.helpers import build_service, prepare_project


def test_same_lifecycle_coordinator_serves_both_typed_application_specs() -> None:
    service = build_service()
    document_project_id, _ = prepare_project(service)
    advisor = service.create_advisor_project(
        name="Synthetic Advisor",
        problem="Compare fictional requirements.",
        users="Architecture testers.",
        outcome="Transparent deterministic results.",
    )
    service.build_advisor_working_version(advisor.id)

    document_spec = service.lifecycle.specification(document_project_id)
    advisor_spec = service.lifecycle.specification(advisor.id)
    document_report = service.lifecycle.evaluate(document_project_id)
    advisor_report = service.lifecycle.evaluate(advisor.id)

    assert document_spec.application_type == ApplicationType.ASK_MY_DOCUMENTS
    assert advisor_spec.application_type == (ApplicationType.ELIGIBILITY_RECOMMENDATION_ADVISOR)
    assert document_report.behavioral_specification_schema.startswith("ask-my-documents.")
    assert advisor_report.behavioral_specification_schema.startswith("eligibility-advisor.")


def test_application_workflows_reject_cross_application_runtime_calls() -> None:
    service = build_service()
    document_project_id, _ = prepare_project(service)
    advisor = service.create_advisor_project(
        name="Synthetic Advisor",
        problem="Compare fictional requirements.",
        users="Architecture testers.",
        outcome="Transparent deterministic results.",
    )
    service.build_advisor_working_version(advisor.id)

    with pytest.raises(ValidationError, match="Ask My Documents"):
        service.ask_question(advisor.id, "Read documents")
    with pytest.raises(ValidationError, match="Eligibility Advisor"):
        service.advisor.test(
            document_project_id,
            AdvisorInput(3.0, ("Algebra", "Academic Writing"), "Computing Foundations"),
        )


def test_unknown_project_application_type_fails_closed() -> None:
    service = build_service()
    project = service.create_project("Unknown type")
    project.metadata["template"] = "UNKNOWN_APPLICATION"
    service.repository.save_project(project)

    with pytest.raises(ValueError, match="UNKNOWN_APPLICATION"):
        service.lifecycle.application_type(project)


def test_working_version_persists_dispatch_identity_and_rejects_wrong_schema() -> None:
    service = build_service()
    advisor = service.create_advisor_project(
        name="Schema-bound Advisor",
        problem="Compare fictional requirements.",
        users="Architecture testers.",
        outcome="Transparent deterministic results.",
    )
    version = service.build_advisor_working_version(advisor.id)
    assert version.assistant_config["template"] == "ELIGIBILITY_RECOMMENDATION_ADVISOR"
    assert version.assistant_config["behavioral_schema"] == "eligibility-advisor.behavior.v1"

    service.repository.save_version(
        replace(
            version,
            assistant_config={**version.assistant_config, "behavioral_schema": "unknown.v99"},
        )
    )
    with pytest.raises(ValueError, match="schema does not match"):
        service.get_application_specification(advisor.id)
