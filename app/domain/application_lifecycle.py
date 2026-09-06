"""Typed lifecycle concepts for an Aqlio-created application.

These records define the Phase A domain boundary. They do not implement approval,
source-code export, or external deployment.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType


class ApplicationType(StrEnum):
    ASK_MY_DOCUMENTS = "ASK_MY_DOCUMENTS"
    ELIGIBILITY_RECOMMENDATION_ADVISOR = "ELIGIBILITY_RECOMMENDATION_ADVISOR"


class ImprovementCategory(StrEnum):
    FUNCTIONALITY = "FUNCTIONALITY"
    LOOK_AND_EXPERIENCE = "LOOK_AND_EXPERIENCE"


class ImprovementStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPLIED = "APPLIED"
    UNSUPPORTED = "UNSUPPORTED"


class VersionApprovalState(StrEnum):
    WORKING = "WORKING"
    APPROVED = "APPROVED"


class ExportPackageStatus(StrEnum):
    REQUESTED = "REQUESTED"
    VALIDATING = "VALIDATING"
    READY = "READY"
    FAILED = "FAILED"


class TaskCapability(StrEnum):
    FACTUAL_ANSWER = "FACTUAL_ANSWER"
    COMPLETE_LIST = "COMPLETE_LIST"
    SUMMARY = "SUMMARY"
    COMPARISON = "COMPARISON"


class EvaluationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_YET_TESTED = "NOT_YET_TESTED"


@dataclass(frozen=True, slots=True)
class AcceptanceCriterion:
    id: str
    requirement_id: str
    description: str
    deterministic: bool = True


@dataclass(frozen=True, slots=True)
class BehavioralRequirement:
    id: str
    description: str
    required: bool
    acceptance_criterion_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BehavioralSpecification:
    schema_version: str
    problem: str
    intended_users: str
    intended_outcome: str
    supported_tasks: tuple[TaskCapability, ...]
    required_inputs: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    grounding_required: bool
    citations_required: bool
    abstention_required: bool
    completeness_required: bool
    ui_requirements: Mapping[str, str]
    constraints: tuple[str, ...]
    requirements: tuple[BehavioralRequirement, ...]
    acceptance_criteria: tuple[AcceptanceCriterion, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "ui_requirements", MappingProxyType(dict(self.ui_requirements)))


@dataclass(frozen=True, slots=True)
class StructuredInputField:
    name: str
    value_type: str
    required: bool
    description: str


@dataclass(frozen=True, slots=True)
class DecisionRule:
    id: str
    program: str
    description: str
    minimum_gpa: float
    prerequisite_courses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AdvisorBehavioralSpecification:
    """Typed contract owned by the bounded eligibility-advisor application type."""

    schema_version: str
    problem: str
    intended_users: str
    intended_outcome: str
    input_schema: tuple[StructuredInputField, ...]
    validation_requirements: tuple[str, ...]
    decision_rules: tuple[DecisionRule, ...]
    expected_output_schema: tuple[str, ...]
    explanation_requirements: tuple[str, ...]
    recommendation_requirements: tuple[str, ...]
    prohibited_behaviors: tuple[str, ...]
    ui_requirements: Mapping[str, str]
    stable_behavioral_requirements: tuple[BehavioralRequirement, ...]
    acceptance_criteria: tuple[AcceptanceCriterion, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "ui_requirements", MappingProxyType(dict(self.ui_requirements)))

    @property
    def requirements(self) -> tuple[BehavioralRequirement, ...]:
        """Template-neutral traceability view used by lifecycle orchestration."""
        return self.stable_behavioral_requirements


@dataclass(frozen=True, slots=True)
class ParticipantValidationEvidence:
    id: str
    project_version_id: str
    participant_user_id: str
    input_summary: str
    validated_at: datetime
    outcome: str = "CONFIRMED_SUCCESS"


@dataclass(frozen=True, slots=True)
class RequirementEvaluation:
    requirement_id: str
    acceptance_criterion_id: str
    status: EvaluationStatus
    explanation: str


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    id: str
    project_version_id: str
    behavioral_specification_schema: str
    results: tuple[RequirementEvaluation, ...]
    evaluated_at: datetime


@dataclass(frozen=True, slots=True)
class ApplicationSpecification:
    """Versioned description shared by the Aqlio runtime and a future export builder."""

    project_id: str
    project_version_id: str
    application_type: ApplicationType
    name: str
    description: str
    behavior_config: Mapping[str, str]
    ui_config: Mapping[str, str]
    document_asset_ids: tuple[str, ...]
    approval_state: VersionApprovalState = VersionApprovalState.WORKING
    behavioral_specification: BehavioralSpecification | AdvisorBehavioralSpecification | None = None
    evaluation_report: EvaluationReport | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "behavior_config", MappingProxyType(dict(self.behavior_config)))
        object.__setattr__(self, "ui_config", MappingProxyType(dict(self.ui_config)))


@dataclass(frozen=True, slots=True)
class ApprovedVersionSnapshot:
    """Immutable approval of the exact specification a participant accepted."""

    id: str
    owner_user_id: str
    workspace_id: str
    specification: ApplicationSpecification
    approved_at: datetime
    participant_validation: ParticipantValidationEvidence | None = None


@dataclass(frozen=True, slots=True)
class ExportPackage:
    """Immutable, owner-scoped record for a validated standalone package."""

    id: str
    approved_snapshot_id: str
    owner_user_id: str
    workspace_id: str
    project_id: str
    project_version_id: str
    export_version: int
    status: ExportPackageStatus
    storage_key: str
    filename: str
    sha256: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ExportProvenance:
    application_type: ApplicationType
    project_id: str
    project_version_id: str
    approved_snapshot_id: str
    behavioral_specification_schema: str
    evaluation_report_id: str
    participant_validation_id: str | None
    approved_at: datetime
