"""Template-neutral specification, evaluation, and provenance orchestration."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime
from typing import Any, Protocol

from app.domain import (
    ApplicationType,
    ApprovedVersionSnapshot,
    EvaluationReport,
    EvaluationStatus,
    ExportProvenance,
    RequirementEvaluation,
)


class TraceableSpecification(Protocol):
    schema_version: str
    requirements: tuple[Any, ...]
    acceptance_criteria: tuple[Any, ...]


class ApplicationTypeAdapter(Protocol):
    application_type: ApplicationType

    def build_specification(self, **context: Any) -> Any: ...

    def evaluate(
        self,
        specification: Any,
        *,
        report_id: str,
        project_version_id: str,
        evaluated_at: datetime,
        context: Mapping[str, object],
    ) -> EvaluationReport: ...

    def specification_to_dict(self, specification: Any) -> dict[str, object]: ...

    def specification_from_dict(self, payload: dict[str, Any]) -> Any: ...


class SpecificationRegistry:
    def __init__(self, adapters: tuple[ApplicationTypeAdapter, ...]) -> None:
        self._adapters = {adapter.application_type: adapter for adapter in adapters}

    def for_type(self, application_type: ApplicationType) -> ApplicationTypeAdapter:
        try:
            return self._adapters[application_type]
        except KeyError as exc:
            raise ValueError(f"Unsupported application type: {application_type}") from exc

    def for_schema(self, schema_version: str) -> ApplicationTypeAdapter:
        for adapter in self._adapters.values():
            if schema_version.startswith(adapter.application_type.value.lower().replace("_", "-")):
                return adapter
            if (
                adapter.application_type == ApplicationType.ASK_MY_DOCUMENTS
                and schema_version.startswith("ask-my-documents.")
            ):
                return adapter
            if (
                adapter.application_type == ApplicationType.ELIGIBILITY_RECOMMENDATION_ADVISOR
                and schema_version.startswith("eligibility-advisor.")
            ):
                return adapter
        raise ValueError(f"Unsupported Behavioral Specification schema: {schema_version}")


def default_specification_registry() -> SpecificationRegistry:
    # Local imports keep type implementations behind this template-neutral boundary.
    from app.application.behavioral_evaluation import AskMyDocumentsAdapter
    from app.application.eligibility_advisor import EligibilityAdvisorAdapter

    return SpecificationRegistry((AskMyDocumentsAdapter(), EligibilityAdvisorAdapter()))


def specification_to_dict(specification: Any) -> dict[str, object]:
    adapter = default_specification_registry().for_schema(specification.schema_version)
    return adapter.specification_to_dict(specification)


def specification_from_dict(
    payload: dict[str, Any], expected_application_type: ApplicationType | None = None
) -> Any:
    adapter = default_specification_registry().for_schema(str(payload["schema_version"]))
    if (
        expected_application_type is not None
        and adapter.application_type != expected_application_type
    ):
        raise ValueError(
            "Behavioral Specification schema does not match the persisted application type."
        )
    return adapter.specification_from_dict(payload)


def export_provenance(snapshot: ApprovedVersionSnapshot) -> ExportProvenance:
    behavioral = snapshot.specification.behavioral_specification
    report = snapshot.specification.evaluation_report
    if behavioral is None or report is None:
        raise ValueError("Approved Version is missing specification or evaluation provenance.")
    return ExportProvenance(
        application_type=snapshot.specification.application_type,
        project_id=snapshot.specification.project_id,
        project_version_id=snapshot.specification.project_version_id,
        approved_snapshot_id=snapshot.id,
        behavioral_specification_schema=behavioral.schema_version,
        evaluation_report_id=report.id,
        participant_validation_id=(
            snapshot.participant_validation.id if snapshot.participant_validation else None
        ),
        approved_at=snapshot.approved_at,
    )


def required_criteria_passed(specification: Any, report: EvaluationReport | None) -> bool:
    if report is None:
        return False
    required_ids = {
        criterion_id
        for requirement in specification.requirements
        if requirement.required
        for criterion_id in requirement.acceptance_criterion_ids
    }
    statuses = {item.acceptance_criterion_id: item.status for item in report.results}
    return report.project_version_id != "" and all(
        statuses.get(criterion_id) == EvaluationStatus.PASS for criterion_id in required_ids
    )


def report_to_json(report: EvaluationReport) -> str:
    return json.dumps(asdict(report), sort_keys=True, default=str)


def report_from_json(value: str) -> EvaluationReport:
    payload = json.loads(value)
    return EvaluationReport(
        payload["id"],
        payload["project_version_id"],
        payload["behavioral_specification_schema"],
        tuple(
            RequirementEvaluation(
                item["requirement_id"],
                item["acceptance_criterion_id"],
                EvaluationStatus(item["status"]),
                item["explanation"],
            )
            for item in payload["results"]
        ),
        datetime.fromisoformat(payload["evaluated_at"]),
    )
