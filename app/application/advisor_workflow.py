"""Application-specific workflow for the bounded synthetic Eligibility Advisor."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import replace

from app.application.eligibility_advisor import AdvisorInput, AdvisorResult, evaluate_eligibility
from app.application.errors import NotReadyError, ValidationError
from app.application.lifecycle_coordinator import LifecycleCoordinator
from app.domain import ApplicationType, Project, ProjectStatus, ProjectVersion
from app.ports import ClockPort, IdPort, M0RepositoryPort


class AdvisorWorkflowService:
    """Owns Advisor build, runtime, and improvement behavior only."""

    def __init__(
        self,
        *,
        clock: ClockPort,
        ids: IdPort,
        repository: M0RepositoryPort,
        lifecycle: LifecycleCoordinator,
        authorized_project: Callable[[str], Project],
        create_project: Callable[[str, str, ApplicationType], Project],
        lifecycle_event: Callable[[str, str, dict[str, str]], None],
        clean_text: Callable[[str], str],
    ) -> None:
        self.clock = clock
        self.ids = ids
        self.repository = repository
        self.lifecycle = lifecycle
        self.authorized_project = authorized_project
        self.create_project = create_project
        self.lifecycle_event = lifecycle_event
        self.clean_text = clean_text

    def create(self, *, name: str, problem: str, users: str, outcome: str) -> Project:
        project = self.create_project(
            name, problem, ApplicationType.ELIGIBILITY_RECOMMENDATION_ADVISOR
        )
        project.metadata.update(
            {
                "idea": "Check synthetic program eligibility and recommend next actions.",
                "problem": self.clean_text(problem),
                "users": self.clean_text(users),
                "outcome": self.clean_text(outcome),
                "defined": "true",
            }
        )
        if not all(project.metadata.get(key) for key in ("problem", "users", "outcome")):
            raise ValidationError("Describe the Advisor's problem, users, and intended outcome.")
        self.repository.save_project(project)
        self.lifecycle_event(
            project.id,
            "SOLUTION_DEFINED",
            {"application_type": ApplicationType.ELIGIBILITY_RECOMMENDATION_ADVISOR.value},
        )
        return project

    def build(self, project_id: str) -> ProjectVersion:
        project = self._advisor_project(project_id)
        if project.current_version_id:
            version = self.repository.get_version(project.current_version_id)
            if version is not None:
                return version
        version = ProjectVersion(
            self.ids.new_id(),
            project.workspace_id,
            project.id,
            self.repository.version_count(project.id) + 1,
            (),
            {
                "template": ApplicationType.ELIGIBILITY_RECOMMENDATION_ADVISOR.value,
                "behavioral_schema": "eligibility-advisor.behavior.v1",
                "spec_problem": project.metadata["problem"],
                "spec_users": project.metadata["users"],
                "spec_outcome": project.metadata["outcome"],
                "ui_title": project.name,
                "ui_instructions": (
                    "Enter synthetic applicant details to check configured requirements."
                ),
                "ui_result_layout": "sections",
                "ui_display_density": "balanced",
                "recommendation_style": "direct",
            },
            self.clock.now(),
        )
        self.repository.save_version(version)
        project.current_version_id = version.id
        project.status = ProjectStatus.PREPARED
        project.updated_at = self.clock.now()
        self.repository.save_project(project)
        self.lifecycle_event(project.id, "WORKING_VERSION_BUILT", {"version_id": version.id})
        return version

    def test(self, project_id: str, value: AdvisorInput) -> AdvisorResult:
        project = self._advisor_project(project_id)
        if not project.current_version_id:
            raise NotReadyError("Build the Advisor Working Version before testing it.")
        result = evaluate_eligibility(value)
        correlation_id = self.ids.new_id()
        project.metadata["pending_test_correlation_id"] = correlation_id
        project.metadata["pending_test_version_id"] = project.current_version_id
        project.metadata["pending_test_question_summary"] = hashlib.sha256(
            repr(value).encode()
        ).hexdigest()[:12]
        project.metadata["pending_test_asset_ids"] = ""
        project.metadata["pending_test_abstained"] = "false"
        project.metadata["advisor_last_test_correlation_id"] = correlation_id
        self.repository.save_project(project)
        self.lifecycle_event(
            project.id, "ADVISOR_TEST_RUN", {"version_id": project.current_version_id}
        )
        return result

    def confirm_test(self, project_id: str) -> Project:
        project = self._advisor_project(project_id)
        return self.lifecycle.confirm_participant_validation(
            project_id, project.metadata.get("advisor_last_test_correlation_id", "")
        )

    def improve(
        self,
        project_id: str,
        request: str,
        *,
        title: str | None = None,
        recommendation_style: str = "direct",
    ) -> ProjectVersion:
        project = self._advisor_project(project_id)
        request = self.clean_text(request)
        if not request or recommendation_style not in {"direct", "supportive"}:
            raise ValidationError(
                "Describe the change and choose a supported recommendation style."
            )
        current = self.repository.get_version(project.current_version_id or "")
        if current is None:
            raise NotReadyError("Build the Advisor Working Version before improving it.")
        clean_title = (
            self.clean_text(title)
            if title is not None
            else current.assistant_config.get("ui_title", project.name)
        )
        if not clean_title:
            raise ValidationError("Provide a title for the Working Version.")
        version = replace(
            current,
            id=self.ids.new_id(),
            number=self.repository.version_count(project.id) + 1,
            assistant_config={
                **current.assistant_config,
                "ui_title": clean_title,
                "recommendation_style": recommendation_style,
                "improvement_request": request,
            },
            created_at=self.clock.now(),
        )
        self.repository.save_version(version)
        project.current_version_id = version.id
        self.lifecycle.invalidate(project)
        self.repository.save_project(project)
        self.lifecycle_event(project.id, "DRAFT_IMPROVED", {"version_id": version.id})
        return version

    def _advisor_project(self, project_id: str) -> Project:
        project = self.authorized_project(project_id)
        if self.lifecycle.application_type(project) != (
            ApplicationType.ELIGIBILITY_RECOMMENDATION_ADVISOR
        ):
            raise ValidationError("This action belongs to the Eligibility Advisor.")
        return project
