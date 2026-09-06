import io
import json
import zipfile
from dataclasses import replace

import pytest

from app.application.behavioral_evaluation import report_to_json
from app.application.errors import NotReadyError, ValidationError
from app.domain import EvaluationStatus
from tests.helpers import build_service, prepare_project


def confirm_participant_test(service, project_id: str) -> None:
    answer = service.ask_question(project_id, "When is annual leave available?", guided=True)
    service.confirm_test_success(project_id, answer.correlation_id)


def test_behavioral_specification_is_typed_traceable_and_uses_participant_intent() -> None:
    service = build_service()
    project = service.create_idea("Help researchers understand field notes")
    service.update_definition(
        project.id,
        {
            "problem": "Facts are difficult to locate",
            "users": "Field researchers",
            "outcome": "Reliable cited answers",
            "ai_role": "Answer and compare field notes",
            "information": "Authorized research notes",
        },
    )
    service.define_solution(project.id)
    service.add_and_prepare_document(project.id, "notes.txt", b"Survey starts in October.")

    specification = service.get_application_specification(project.id)
    behavioral = specification.behavioral_specification

    assert behavioral is not None
    assert behavioral.problem == "Facts are difficult to locate"
    assert behavioral.intended_users == "Field researchers"
    assert behavioral.intended_outcome == "Reliable cited answers"
    criterion_ids = {item.id for item in behavioral.acceptance_criteria}
    assert all(
        requirement.acceptance_criterion_ids
        and set(requirement.acceptance_criterion_ids) <= criterion_ids
        for requirement in behavioral.requirements
    )
    assert {item.id for item in behavioral.requirements} >= {
        "AMD-FACT-001",
        "AMD-LIST-001",
        "AMD-SUMMARY-001",
        "AMD-COMPARE-001",
        "AMD-CITE-001",
        "AMD-ABSTAIN-001",
        "AMD-INJECT-001",
        "AMD-UI-001",
    }
    with pytest.raises(ValidationError, match="already part of the Working Version"):
        service.update_definition(project.id, {"outcome": "A mutable different outcome"})
    assert (
        service.get_application_specification(project.id).behavioral_specification.intended_outcome
        == "Reliable cited answers"
    )


def test_evaluation_states_are_version_specific_and_improvements_require_regression() -> None:
    service = build_service()
    project_id, _ = prepare_project(service, "Museum guide")

    before = service.get_application_specification(project_id)
    assert before.evaluation_report is None
    report = service.evaluate_working_version(project_id)
    statuses = {item.requirement_id: item.status for item in report.results}
    assert all(
        status == EvaluationStatus.PASS
        for requirement_id, status in statuses.items()
        if requirement_id != "AMD-MANAGED-001"
    )
    assert statuses["AMD-MANAGED-001"] == EvaluationStatus.NOT_YET_TESTED

    old_version = report.project_version_id
    service.apply_improvement(project_id, "Use clearer answers", response_style="balanced")
    changed = service.get_application_specification(project_id)
    assert changed.project_version_id != old_version
    assert changed.evaluation_report is None
    rerun = service.evaluate_working_version(project_id)
    assert rerun.project_version_id == changed.project_version_id


def test_failed_requirement_flows_to_improvement_and_new_version() -> None:
    service = build_service()
    project_id, _ = prepare_project(service, "Course guide")
    report = service.evaluate_working_version(project_id)
    failed_result = replace(
        report.results[0], status=EvaluationStatus.FAIL, explanation="Input failed."
    )
    failed_report = replace(report, results=(failed_result, *report.results[1:]))
    project = service.get_my_project(project_id)
    project.metadata["behavioral_evaluation"] = report_to_json(failed_report)
    service.repository.save_project(project)

    service.improve_failed_evaluation(project_id)
    prepared = service.get_my_project(project_id)
    assert "AMD-INPUT-001" in prepared.metadata["improvement_feedback"]
    previous_version = prepared.current_version_id
    service.apply_improvement(
        project_id,
        prepared.metadata["improvement_feedback"],
        response_style="balanced",
    )
    assert service.get_my_project(project_id).current_version_id != previous_version
    assert service.get_application_specification(project_id).evaluation_report is None


def test_approval_requires_required_evaluation_and_snapshots_provenance() -> None:
    service = build_service()
    project_id, _ = prepare_project(service)
    confirm_participant_test(service, project_id)
    project = service.get_my_project(project_id)
    project.metadata.pop("behavioral_evaluation")
    service.repository.save_project(project)

    with pytest.raises(NotReadyError, match="behavioral acceptance criterion"):
        service.approve_working_version(project_id)

    report = service.evaluate_working_version(project_id)
    approved = service.approve_working_version(project_id)
    assert approved.specification.evaluation_report == report
    assert approved.specification.behavioral_specification is not None

    package = service.generate_application_export(project_id)
    download = service.download_application_export(package.id)
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        manifest = json.loads(archive.read("AQLIO_EXPORT_MANIFEST.json"))
        config = json.loads(archive.read("application_config.json"))
    assert manifest["Behavioral Specification Schema"] == "ask-my-documents.behavior.v1"
    assert manifest["Evaluation Report"]["id"] == report.id
    assert config["behavioral_specification"]["requirements"]
