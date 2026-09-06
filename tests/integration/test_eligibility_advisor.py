from dataclasses import FrozenInstanceError

import pytest

from app.application.eligibility_advisor import AdvisorInput, evaluate_eligibility
from app.application.errors import NotReadyError, ValidationError
from app.application.specification_lifecycle import (
    export_provenance,
    required_criteria_passed,
    specification_from_dict,
    specification_to_dict,
)
from app.domain import ApplicationType, EvaluationStatus
from tests.helpers import build_service


def build_advisor(service):
    project = service.create_advisor_project(
        name="Synthetic Program Advisor",
        problem="Requirements are difficult to compare.",
        users="People testing fictional application scenarios.",
        outcome="A transparent deterministic eligibility result and next actions.",
    )
    version = service.build_advisor_working_version(project.id)
    return project.id, version.id


def test_advisor_behavioral_specification_is_typed_stable_and_traceable() -> None:
    service = build_service()
    project_id, _ = build_advisor(service)
    specification = service.get_application_specification(project_id)
    behavioral = specification.behavioral_specification

    assert specification.application_type == ApplicationType.ELIGIBILITY_RECOMMENDATION_ADVISOR
    assert behavioral.schema_version == "eligibility-advisor.behavior.v1"
    assert {item.name for item in behavioral.input_schema} == {
        "gpa",
        "completed_prerequisites",
        "target_program",
    }
    assert len(behavioral.decision_rules) == 2
    assert behavioral.expected_output_schema == (
        "eligibility_status",
        "explanation",
        "satisfied_requirements",
        "unmet_requirements",
        "recommended_next_actions",
        "rule_ids",
        "disclaimer",
    )
    criterion_ids = {item.id for item in behavioral.acceptance_criteria}
    assert all(
        set(item.acceptance_criterion_ids) <= criterion_ids for item in behavioral.requirements
    )
    assert all(item.id.startswith("ADV-") for item in behavioral.requirements)
    assert specification_from_dict(specification_to_dict(behavioral)) == behavioral


def test_advisor_decision_cases_are_deterministic_and_explanations_match() -> None:
    eligible = evaluate_eligibility(
        AdvisorInput(3.2, ("Algebra", "Academic Writing"), "Computing Foundations")
    )
    boundary = evaluate_eligibility(
        AdvisorInput(3.0, ("Algebra", "Academic Writing"), "Computing Foundations")
    )
    missing = evaluate_eligibility(AdvisorInput(3.7, ("Algebra",), "Computing Foundations"))
    multiple = evaluate_eligibility(AdvisorInput(2.0, (), "Computing Foundations"))

    assert eligible.eligibility_status == boundary.eligibility_status == "ELIGIBLE"
    assert missing.unmet_requirements == ("Missing prerequisite: Academic Writing.",)
    assert "1 configured requirement" in missing.explanation
    assert any("Academic Writing" in item for item in missing.recommended_next_actions)
    assert len(multiple.unmet_requirements) == 3
    assert "not a real admission prediction" in eligible.disclaimer
    with pytest.raises(ValidationError):
        evaluate_eligibility(AdvisorInput(4.1, (), "Computing Foundations"))
    with pytest.raises(ValidationError):
        evaluate_eligibility(AdvisorInput(3.0, (), ""))


def test_advisor_evaluation_reports_every_claim_and_requires_participant_validation() -> None:
    service = build_service()
    project_id, _ = build_advisor(service)
    specification = service.get_application_specification(project_id)
    assert specification.evaluation_report is None
    with pytest.raises(NotReadyError):
        service.approve_working_version(project_id)

    report = service.evaluate_working_version(project_id)
    assert len(report.results) == 10
    assert {item.status for item in report.results} == {EvaluationStatus.PASS}
    assert required_criteria_passed(specification.behavioral_specification, report)
    with pytest.raises(NotReadyError, match="confirm a successful"):
        service.approve_working_version(project_id)

    service.test_advisor(project_id, AdvisorInput(2.7, ("Studio Basics",), "Design Studies"))
    service.confirm_advisor_test_success(project_id)
    approved = service.approve_working_version(project_id)
    provenance = export_provenance(approved)
    assert provenance.behavioral_specification_schema == "eligibility-advisor.behavior.v1"
    assert provenance.evaluation_report_id == approved.specification.evaluation_report.id
    assert approved.specification.evaluation_report.project_version_id == report.project_version_id
    assert provenance.participant_validation_id == approved.participant_validation.id
    assert provenance.approved_at == approved.approved_at
    with pytest.raises(FrozenInstanceError):
        provenance.project_version_id = "changed"  # type: ignore[misc]


def test_advisor_improvement_creates_new_working_version_and_preserves_approval() -> None:
    service = build_service()
    project_id, old_version_id = build_advisor(service)
    service.test_advisor(
        project_id, AdvisorInput(3.5, ("Algebra", "Academic Writing"), "Computing Foundations")
    )
    service.confirm_advisor_test_success(project_id)
    old_report = service.get_application_specification(project_id).evaluation_report
    approved = service.approve_working_version(project_id)

    changed = service.apply_advisor_improvement(
        project_id,
        "Use a friendlier recommendation tone.",
        title="Synthetic Eligibility Guide",
        recommendation_style="supportive",
    )
    assert changed.id != old_version_id
    current = service.get_application_specification(project_id)
    assert current.evaluation_report is None
    assert service.get_my_project(project_id).guided_test_count == 0
    assert (
        service.get_approved_version(approved.id).specification.project_version_id == old_version_id
    )
    assert service.get_approved_version(approved.id).specification.evaluation_report == old_report
    with pytest.raises(NotReadyError):
        service.approve_working_version(project_id)

    rerun = service.evaluate_working_version(project_id)
    assert rerun.project_version_id == changed.id
    service.test_advisor(
        project_id, AdvisorInput(2.5, ("Studio Basics", "Academic Writing"), "Design Studies")
    )
    service.confirm_advisor_test_success(project_id)
    newer = service.approve_working_version(project_id)
    assert newer.id != approved.id
