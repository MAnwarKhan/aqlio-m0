"""Shared exact-version lifecycle orchestration for typed application specifications."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from app.application.errors import NotReadyError, ValidationError
from app.application.specification_lifecycle import (
    SpecificationRegistry,
    export_provenance,
    report_from_json,
    report_to_json,
    required_criteria_passed,
)
from app.domain import (
    ApplicationSpecification,
    ApplicationType,
    ApprovedVersionSnapshot,
    EvaluationReport,
    EvaluationStatus,
    ExportProvenance,
    GuidedTest,
    ParticipantValidationEvidence,
    Project,
    ProjectStatus,
    VersionApprovalState,
    transition_project,
)
from app.ports import AuthPort, ClockPort, IdPort, M0RepositoryPort


class LifecycleCoordinator:
    """Owns lifecycle mechanics, never application-specific runtime behavior."""

    def __init__(
        self,
        *,
        auth: AuthPort,
        clock: ClockPort,
        ids: IdPort,
        repository: M0RepositoryPort,
        registry: SpecificationRegistry,
        authorized_project: Callable[[str], Project],
        lifecycle_event: Callable[[str, str, dict[str, str]], None],
    ) -> None:
        self.auth = auth
        self.clock = clock
        self.ids = ids
        self.repository = repository
        self.registry = registry
        self.authorized_project = authorized_project
        self.lifecycle_event = lifecycle_event

    @staticmethod
    def application_type(project: Project) -> ApplicationType:
        value = project.metadata.get("template")
        if value is None:
            return ApplicationType.ASK_MY_DOCUMENTS
        return ApplicationType(value)

    def specification(self, project_id: str) -> ApplicationSpecification:
        project = self.authorized_project(project_id)
        version = self.repository.get_version(project.current_version_id or "")
        if version is None:
            raise NotReadyError("Build your Working Version first.")
        config = dict(version.assistant_config)
        ui_config = {
            key.removeprefix("ui_"): value for key, value in config.items() if key.startswith("ui_")
        }
        application_type = self.application_type(project)
        persisted_type = config.get("application_type", config.get("template"))
        if persisted_type is not None and persisted_type != application_type.value:
            raise ValueError(
                "Working Version application type does not match its persisted project type."
            )
        behavioral = self.registry.for_type(application_type).build_specification(
            problem=config.get(
                "spec_problem", project.metadata.get("problem", project.description)
            ),
            users=config.get("spec_users", project.metadata.get("users", "")),
            outcome=config.get("spec_outcome", project.metadata.get("outcome", "")),
            ui_config=ui_config,
        )
        persisted_schema = config.get("behavioral_schema")
        if persisted_schema is not None and persisted_schema != behavioral.schema_version:
            raise ValueError(
                "Working Version schema does not match its typed Behavioral Specification."
            )
        report = None
        if saved_report := project.metadata.get("behavioral_evaluation"):
            parsed = report_from_json(saved_report)
            if parsed.project_version_id == version.id:
                report = parsed
        return ApplicationSpecification(
            project_id=project.id,
            project_version_id=version.id,
            application_type=application_type,
            name=config.get("ui_title", project.name),
            description=config.get("ui_instructions", project.description),
            behavior_config={
                key: value for key, value in config.items() if not key.startswith(("ui_", "spec_"))
            },
            ui_config=ui_config,
            document_asset_ids=version.asset_ids,
            approval_state=VersionApprovalState.WORKING,
            behavioral_specification=behavioral,
            evaluation_report=report,
        )

    def evaluate(self, project_id: str) -> EvaluationReport:
        project = self.authorized_project(project_id)
        specification = self.specification(project_id)
        behavioral = specification.behavioral_specification
        if behavioral is None:
            raise NotReadyError("Build the Behavioral Specification before evaluation.")
        report = self.registry.for_type(specification.application_type).evaluate(
            behavioral,
            report_id=self.ids.new_id(),
            project_version_id=specification.project_version_id,
            evaluated_at=self.clock.now(),
            context={"prepared_document_count": project.prepared_document_count},
        )
        project.metadata["behavioral_evaluation"] = report_to_json(report)
        self.repository.save_project(project)
        self.lifecycle_event(
            project.id,
            "BEHAVIORAL_EVALUATION_COMPLETED",
            {
                "version_id": specification.project_version_id,
                "required_passed": str(required_criteria_passed(behavioral, report)).lower(),
            },
        )
        return report

    def confirm_participant_validation(self, project_id: str, correlation_id: str) -> Project:
        project = self.authorized_project(project_id)
        if (
            project.metadata.get("pending_test_correlation_id") != correlation_id
            or project.metadata.get("pending_test_version_id") != project.current_version_id
        ):
            raise ValidationError("Test the current Working Version before confirming it.")
        if project.metadata.get("pending_test_abstained") == "true":
            raise ValidationError("An unanswered question cannot confirm the Working Version.")
        test = GuidedTest(
            id=self.ids.new_id(),
            project_id=project.id,
            project_version_id=project.current_version_id or "",
            user_id=self.auth.current_user().id,
            question_summary=project.metadata["pending_test_question_summary"],
            cited_asset_ids=tuple(
                item
                for item in project.metadata.get("pending_test_asset_ids", "").split(",")
                if item
            ),
            completed_at=self.clock.now(),
        )
        self.repository.save_guided_test(test)
        project.guided_test_count += 1
        project.metadata["last_confirmed_test_version_id"] = project.current_version_id or ""
        if project.status == ProjectStatus.PREPARED:
            transition_project(project, ProjectStatus.TESTED)
        self.clear_pending_test(project)
        project.metadata.pop("improvement_feedback", None)
        self.repository.save_project(project)
        self.lifecycle_event(project.id, "TEST_CONFIRMED", {"test_id": test.id})
        self.evaluate(project_id)
        return self.authorized_project(project_id)

    def invalidate(self, project: Project) -> None:
        project.guided_test_count = 0
        project.readiness_confirmed = False
        project.metadata.pop("run_version_id", None)
        project.metadata.pop("last_confirmed_test_version_id", None)
        project.metadata.pop("behavioral_evaluation", None)
        self.clear_pending_test(project)
        if project.status in {ProjectStatus.TESTED, ProjectStatus.READY, ProjectStatus.DEPLOYED}:
            transition_project(project, ProjectStatus.PREPARED)
        project.updated_at = self.clock.now()

    def approve(self, project_id: str) -> ApprovedVersionSnapshot:
        project = self.authorized_project(project_id)
        version_id = project.current_version_id
        if (
            not version_id
            or project.guided_test_count < 1
            or project.metadata.get("last_confirmed_test_version_id") != version_id
        ):
            raise NotReadyError(
                "Test the current Working Version and confirm a successful answer before approval."
            )
        specification = self.specification(project.id)
        behavioral = specification.behavioral_specification
        if behavioral is None or not required_criteria_passed(
            behavioral, specification.evaluation_report
        ):
            raise NotReadyError(
                "Pass every required behavioral acceptance criterion before approval."
            )
        existing = next(
            (
                item
                for item in self.repository.list_approved_versions(project.id)
                if item.specification.project_version_id == version_id
            ),
            None,
        )
        if existing:
            return existing
        tests = [
            item
            for item in self.repository.list_guided_tests(project.id)
            if item.project_version_id == version_id
        ]
        if not tests:
            raise NotReadyError("Participant validation evidence is unavailable for this version.")
        test = max(tests, key=lambda item: item.completed_at)
        approved_specification = replace(
            specification, approval_state=VersionApprovalState.APPROVED
        )
        snapshot = ApprovedVersionSnapshot(
            id=self.ids.new_id(),
            owner_user_id=project.owner_user_id,
            workspace_id=project.workspace_id,
            specification=approved_specification,
            approved_at=self.clock.now(),
            participant_validation=ParticipantValidationEvidence(
                id=test.id,
                project_version_id=test.project_version_id,
                participant_user_id=test.user_id,
                input_summary=test.question_summary,
                validated_at=test.completed_at,
            ),
        )
        self.repository.save_approved_version(snapshot)
        project.metadata["approved_version_id"] = snapshot.id
        self.repository.save_project(project)
        self.lifecycle_event(project.id, "WORKING_VERSION_APPROVED", {"version_id": version_id})
        return snapshot

    def provenance(self, snapshot: ApprovedVersionSnapshot) -> ExportProvenance:
        return export_provenance(snapshot)

    def improve_failed_evaluation(self, project_id: str) -> Project:
        project = self.authorized_project(project_id)
        report = self.specification(project_id).evaluation_report
        if report is None:
            raise ValidationError("Evaluate this Working Version before improving failures.")
        failures = [item for item in report.results if item.status == EvaluationStatus.FAIL]
        if not failures:
            raise ValidationError("This evaluation has no failed requirements to improve.")
        project.metadata["improvement_feedback"] = (
            "Improve behavior with clear results for failed requirements: "
            + ", ".join(item.requirement_id for item in failures)
            + ". "
            + " ".join(item.explanation for item in failures)
        )
        self.repository.save_project(project)
        self.lifecycle_event(project.id, "EVALUATION_FAILURE_SENT_TO_IMPROVEMENT", {})
        return project

    @staticmethod
    def clear_pending_test(project: Project) -> None:
        for key in (
            "pending_test_correlation_id",
            "pending_test_version_id",
            "pending_test_question_summary",
            "pending_test_asset_ids",
            "pending_test_abstained",
        ):
            project.metadata.pop(key, None)
