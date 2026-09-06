"""Deterministic synthetic Eligibility & Recommendation Advisor reference application."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from app.application.errors import ValidationError
from app.domain import (
    AcceptanceCriterion,
    AdvisorBehavioralSpecification,
    ApplicationType,
    BehavioralRequirement,
    DecisionRule,
    EvaluationReport,
    EvaluationStatus,
    RequirementEvaluation,
    StructuredInputField,
)


@dataclass(frozen=True, slots=True)
class AdvisorInput:
    gpa: float
    completed_prerequisites: tuple[str, ...]
    target_program: str


@dataclass(frozen=True, slots=True)
class AdvisorResult:
    eligibility_status: str
    explanation: str
    satisfied_requirements: tuple[str, ...]
    unmet_requirements: tuple[str, ...]
    recommended_next_actions: tuple[str, ...]
    rule_ids: tuple[str, ...]
    disclaimer: str = "Synthetic demonstration only; this is not a real admission prediction."


PROGRAM_RULES = (
    DecisionRule(
        "RULE-CF-001",
        "Computing Foundations",
        "GPA must be at least 3.0 and both prerequisites must be completed.",
        3.0,
        ("Algebra", "Academic Writing"),
    ),
    DecisionRule(
        "RULE-DS-001",
        "Design Studies",
        "GPA must be at least 2.5 and both prerequisites must be completed.",
        2.5,
        ("Studio Basics", "Academic Writing"),
    ),
)


def evaluate_eligibility(value: AdvisorInput) -> AdvisorResult:
    if isinstance(value.gpa, bool) or not isinstance(value.gpa, int | float):
        raise ValidationError("Enter GPA as a number from 0.0 through 4.0.")
    if value.gpa < 0 or value.gpa > 4:
        raise ValidationError("Enter GPA as a number from 0.0 through 4.0.")
    if not value.target_program.strip():
        raise ValidationError("Choose a target program.")
    rule = next((item for item in PROGRAM_RULES if item.program == value.target_program), None)
    if rule is None:
        raise ValidationError("Choose one of the available synthetic programs.")
    normalized = {item.strip().casefold() for item in value.completed_prerequisites if item.strip()}
    satisfied: list[str] = []
    unmet: list[str] = []
    actions: list[str] = []
    if value.gpa >= rule.minimum_gpa:
        satisfied.append(f"GPA is at least {rule.minimum_gpa:.1f}.")
    else:
        unmet.append(f"GPA is below {rule.minimum_gpa:.1f}.")
        actions.append(f"Raise the synthetic GPA to at least {rule.minimum_gpa:.1f}.")
    for course in rule.prerequisite_courses:
        if course.casefold() in normalized:
            satisfied.append(f"Completed prerequisite: {course}.")
        else:
            unmet.append(f"Missing prerequisite: {course}.")
            actions.append(f"Complete the synthetic prerequisite {course}.")
    eligible = not unmet
    if eligible:
        actions.append(
            "Review the synthetic program checklist before submitting a practice application."
        )
    else:
        alternatives = [item.program for item in PROGRAM_RULES if item.program != rule.program]
        actions.append(f"Optionally compare the synthetic requirements for {alternatives[0]}.")
    explanation = (
        f"Eligible under {rule.id}: every configured requirement is satisfied."
        if eligible
        else f"Not eligible under {rule.id}: {len(unmet)} configured requirement(s) are unmet."
    )
    return AdvisorResult(
        "ELIGIBLE" if eligible else "NOT_ELIGIBLE",
        explanation,
        tuple(satisfied),
        tuple(unmet),
        tuple(actions),
        (rule.id,),
    )


def build_advisor_specification(
    *, problem: str, users: str, outcome: str, ui_config: dict[str, str]
) -> AdvisorBehavioralSpecification:
    criteria = (
        AcceptanceCriterion(
            "AC-ADV-ELIGIBLE", "ADV-DECISION-001", "Clearly eligible fixture passes."
        ),
        AcceptanceCriterion(
            "AC-ADV-INELIGIBLE", "ADV-DECISION-001", "Clearly ineligible fixture fails eligibility."
        ),
        AcceptanceCriterion("AC-ADV-BOUNDARY", "ADV-DECISION-001", "Minimum GPA is inclusive."),
        AcceptanceCriterion(
            "AC-ADV-PREREQ", "ADV-DECISION-002", "A missing prerequisite is identified."
        ),
        AcceptanceCriterion(
            "AC-ADV-MULTIPLE", "ADV-DECISION-002", "Multiple unmet requirements are preserved."
        ),
        AcceptanceCriterion(
            "AC-ADV-INVALID", "ADV-INPUT-001", "Missing or invalid input is rejected."
        ),
        AcceptanceCriterion(
            "AC-ADV-EXPLAIN", "ADV-EXPLAIN-001", "Explanation matches evaluated rules."
        ),
        AcceptanceCriterion(
            "AC-ADV-RECOMMEND", "ADV-RECOMMEND-001", "Recommendations match unmet requirements."
        ),
        AcceptanceCriterion(
            "AC-ADV-CLAIMS", "ADV-SAFETY-001", "Output makes no unsupported real-world claim."
        ),
        AcceptanceCriterion("AC-ADV-UI", "ADV-UI-001", "Approved UI behavior is honored."),
    )
    descriptions = {
        "ADV-INPUT-001": (
            "Validate GPA, completed prerequisites, and target program before evaluation."
        ),
        "ADV-DECISION-001": (
            "Apply the selected program's deterministic GPA rule, including its boundary."
        ),
        "ADV-DECISION-002": (
            "Evaluate every configured prerequisite without stopping at the first failure."
        ),
        "ADV-EXPLAIN-001": (
            "Explain eligibility using the actual selected rule and unmet-result count."
        ),
        "ADV-RECOMMEND-001": "Recommend actions directly corresponding to each unmet requirement.",
        "ADV-SAFETY-001": "Use synthetic fixtures and never predict real admission outcomes.",
        "ADV-UI-001": "Honor the approved title, instructions, result layout, and detail choice.",
    }
    requirements = tuple(
        BehavioralRequirement(
            requirement_id,
            description,
            True,
            tuple(item.id for item in criteria if item.requirement_id == requirement_id),
        )
        for requirement_id, description in descriptions.items()
    )
    return AdvisorBehavioralSpecification(
        schema_version="eligibility-advisor.behavior.v1",
        problem=problem
        or "People need a transparent check against synthetic program requirements.",
        intended_users=users or "People testing a fictional university-program scenario.",
        intended_outcome=outcome or "A deterministic status, explanation, gaps, and next actions.",
        input_schema=(
            StructuredInputField("gpa", "number", True, "Synthetic GPA from 0.0 through 4.0."),
            StructuredInputField(
                "completed_prerequisites", "list[string]", True, "Completed synthetic courses."
            ),
            StructuredInputField(
                "target_program", "enum", True, "One configured synthetic program."
            ),
        ),
        validation_requirements=(
            "GPA is numeric and between 0.0 and 4.0 inclusive.",
            "Target program is present and configured.",
            "Prerequisites are evaluated as normalized course names.",
        ),
        decision_rules=PROGRAM_RULES,
        expected_output_schema=(
            "eligibility_status",
            "explanation",
            "satisfied_requirements",
            "unmet_requirements",
            "recommended_next_actions",
            "rule_ids",
            "disclaimer",
        ),
        explanation_requirements=(
            "Name the applied rule.",
            "Reflect the actual unmet count and status.",
        ),
        recommendation_requirements=(
            "Address every unmet requirement.",
            "Offer only configured synthetic alternatives.",
        ),
        prohibited_behaviors=(
            "Do not represent synthetic rules as a real university policy.",
            "Do not predict admission, ranking, scholarship, or applicant success.",
            "Do not infer protected or unprovided attributes.",
        ),
        ui_requirements=ui_config,
        stable_behavioral_requirements=requirements,
        acceptance_criteria=criteria,
    )


def _run_acceptance_checks(
    specification: AdvisorBehavioralSpecification,
) -> dict[str, tuple[bool, str]]:
    eligible = evaluate_eligibility(
        AdvisorInput(3.4, ("Algebra", "Academic Writing"), "Computing Foundations")
    )
    ineligible = evaluate_eligibility(AdvisorInput(2.0, (), "Computing Foundations"))
    boundary = evaluate_eligibility(
        AdvisorInput(3.0, ("Algebra", "Academic Writing"), "Computing Foundations")
    )
    missing = evaluate_eligibility(AdvisorInput(3.5, ("Algebra",), "Computing Foundations"))
    multiple = evaluate_eligibility(AdvisorInput(2.4, (), "Computing Foundations"))
    try:
        evaluate_eligibility(AdvisorInput(4.5, (), "Computing Foundations"))
        invalid_rejected = False
    except ValidationError:
        invalid_rejected = True
    ui = dict(specification.ui_requirements)
    ui_valid = ui.get("result_layout", "sections") in {"sections", "summary"} and ui.get(
        "display_density", "balanced"
    ) in {"concise", "balanced", "detailed"}
    return {
        "AC-ADV-ELIGIBLE": (
            eligible.eligibility_status == "ELIGIBLE" and not eligible.unmet_requirements,
            "Eligible fixture satisfied every configured rule.",
        ),
        "AC-ADV-INELIGIBLE": (
            ineligible.eligibility_status == "NOT_ELIGIBLE" and bool(ineligible.unmet_requirements),
            "Ineligible fixture returned its configured gaps.",
        ),
        "AC-ADV-BOUNDARY": (
            boundary.eligibility_status == "ELIGIBLE",
            "The exact minimum GPA passed.",
        ),
        "AC-ADV-PREREQ": (
            missing.unmet_requirements == ("Missing prerequisite: Academic Writing.",),
            "The missing prerequisite was identified exactly.",
        ),
        "AC-ADV-MULTIPLE": (
            len(multiple.unmet_requirements) == 3,
            "GPA and both missing prerequisites were retained.",
        ),
        "AC-ADV-INVALID": (invalid_rejected, "Out-of-range GPA was rejected before evaluation."),
        "AC-ADV-EXPLAIN": (
            "RULE-CF-001" in missing.explanation and "1 configured" in missing.explanation,
            "Explanation names the applied rule and actual unmet count.",
        ),
        "AC-ADV-RECOMMEND": (
            all(
                any(
                    gap.split(": ")[-1].rstrip(".") in action
                    for action in missing.recommended_next_actions
                )
                for gap in missing.unmet_requirements
            ),
            "Each unmet prerequisite has a corresponding action.",
        ),
        "AC-ADV-CLAIMS": (
            all(
                "real admission" not in result.explanation.casefold()
                for result in (eligible, ineligible, boundary, missing, multiple)
            )
            and "not a real admission prediction" in eligible.disclaimer,
            "Fixtures remain explicitly synthetic and make no admission prediction.",
        ),
        "AC-ADV-UI": (ui_valid, "Structured Advisor UI choices are within the approved values."),
    }


class EligibilityAdvisorAdapter:
    application_type = ApplicationType.ELIGIBILITY_RECOMMENDATION_ADVISOR

    def build_specification(self, **context: Any) -> AdvisorBehavioralSpecification:
        return build_advisor_specification(
            problem=str(context.get("problem", "")),
            users=str(context.get("users", "")),
            outcome=str(context.get("outcome", "")),
            ui_config=dict(context.get("ui_config", {})),
        )

    def evaluate(
        self,
        specification: AdvisorBehavioralSpecification,
        *,
        report_id: str,
        project_version_id: str,
        evaluated_at: datetime,
        context: Mapping[str, object],
    ) -> EvaluationReport:
        checks = _run_acceptance_checks(specification)
        return EvaluationReport(
            report_id,
            project_version_id,
            specification.schema_version,
            tuple(
                RequirementEvaluation(
                    item.requirement_id,
                    item.id,
                    EvaluationStatus.PASS if checks[item.id][0] else EvaluationStatus.FAIL,
                    checks[item.id][1],
                )
                for item in specification.acceptance_criteria
            ),
            evaluated_at,
        )

    def specification_to_dict(
        self, specification: AdvisorBehavioralSpecification
    ) -> dict[str, object]:
        return {
            "schema_version": specification.schema_version,
            "problem": specification.problem,
            "intended_users": specification.intended_users,
            "intended_outcome": specification.intended_outcome,
            "input_schema": [asdict(item) for item in specification.input_schema],
            "validation_requirements": list(specification.validation_requirements),
            "decision_rules": [asdict(item) for item in specification.decision_rules],
            "expected_output_schema": list(specification.expected_output_schema),
            "explanation_requirements": list(specification.explanation_requirements),
            "recommendation_requirements": list(specification.recommendation_requirements),
            "prohibited_behaviors": list(specification.prohibited_behaviors),
            "ui_requirements": dict(specification.ui_requirements),
            "stable_behavioral_requirements": [
                asdict(item) for item in specification.stable_behavioral_requirements
            ],
            "acceptance_criteria": [asdict(item) for item in specification.acceptance_criteria],
        }

    def specification_from_dict(self, payload: dict[str, Any]) -> AdvisorBehavioralSpecification:
        return AdvisorBehavioralSpecification(
            schema_version=str(payload["schema_version"]),
            problem=str(payload["problem"]),
            intended_users=str(payload["intended_users"]),
            intended_outcome=str(payload["intended_outcome"]),
            input_schema=tuple(StructuredInputField(**item) for item in payload["input_schema"]),
            validation_requirements=tuple(payload["validation_requirements"]),
            decision_rules=tuple(
                DecisionRule(
                    item["id"],
                    item["program"],
                    item["description"],
                    float(item["minimum_gpa"]),
                    tuple(item["prerequisite_courses"]),
                )
                for item in payload["decision_rules"]
            ),
            expected_output_schema=tuple(payload["expected_output_schema"]),
            explanation_requirements=tuple(payload["explanation_requirements"]),
            recommendation_requirements=tuple(payload["recommendation_requirements"]),
            prohibited_behaviors=tuple(payload["prohibited_behaviors"]),
            ui_requirements=dict(payload["ui_requirements"]),
            stable_behavioral_requirements=tuple(
                BehavioralRequirement(
                    item["id"],
                    item["description"],
                    bool(item["required"]),
                    tuple(item["acceptance_criterion_ids"]),
                )
                for item in payload["stable_behavioral_requirements"]
            ),
            acceptance_criteria=tuple(
                AcceptanceCriterion(
                    item["id"],
                    item["requirement_id"],
                    item["description"],
                    bool(item["deterministic"]),
                )
                for item in payload["acceptance_criteria"]
            ),
        )
