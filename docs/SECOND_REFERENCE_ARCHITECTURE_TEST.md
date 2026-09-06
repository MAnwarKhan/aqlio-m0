# Bounded second-reference architecture test — 2026-09-06

## Decision

The specification-driven lifecycle supports a second, structurally different reference
application without routing it through document retrieval, generation, citations, or document
fixtures. The test is deliberately bounded to two application types. It adds no arbitrary code
generation, workflow builder, agent, plugin, external integration, managed provider, real
university data, paid call, deployment, or infrastructure provisioning.

## Template-neutral lifecycle

The shared path is now:

`User Intent → Application Type Adapter → Typed Behavioral Specification → Stable Requirements`

`→ Derived Acceptance Criteria → Version-Specific Implementation → Adapter Evaluation`

`→ Participant Validation → Versioned Improvement → Fresh Evaluation → Approval`

`→ Export Provenance`

`ApplicationTypeAdapter` and `SpecificationRegistry` are the narrow orchestration seam. They
dispatch specification construction, deterministic evaluation, and specification serialization by
application type/schema. Shared records retain exact-version evaluation results, Pass/Fail/Not Yet
Tested status, immutable approval snapshots, and export provenance. The registry is closed to the
two approved reference types; it is not an arbitrary application generator.

## Correctly application-specific

- Ask My Documents owns document validation/extraction, chunking, retrieval, question-aware
  answers, grounding, citations, completeness, abstention, injection filtering, its `AMD-*`
  requirements, fixtures, evaluator, runtime, publishing, and standalone export implementation.
- Eligibility & Recommendation Advisor owns structured applicant inputs, synthetic program rules,
  deterministic decision execution, explanations, recommendations, prohibited claims, its
  `ADV-*` requirements, fixtures, evaluator, and participant result UI.
- Publication and standalone runtime generation remain Ask My Documents-specific in this bounded
  phase. Advisor approval and export provenance are proven; Advisor deployment is not.

## Advisor Behavioral Specification

Schema: `eligibility-advisor.behavior.v1`.

- Intent: fictional-program users receive a transparent deterministic status, rule explanation,
  satisfied/unmet requirements, and next actions.
- Inputs: GPA number (0.0–4.0), completed prerequisite names, and one configured target program.
- Validation: reject nonnumeric/out-of-range GPA and absent/unknown programs; normalize course
  names before comparison.
- Rules: two synthetic fixtures only—Computing Foundations (3.0, Algebra, Academic Writing) and
  Design Studies (2.5, Studio Basics, Academic Writing). GPA boundaries are inclusive.
- Outputs: eligibility status, explanation, satisfied requirements, unmet requirements,
  recommended next actions, applied rule IDs, and synthetic-data disclaimer.
- Explanation: name the actual rule and reflect the actual status/unmet count.
- Recommendations: address each unmet requirement and only mention configured synthetic
  alternatives.
- Prohibited: no real policy claim, admission/ranking/scholarship/success prediction, or inference
  of protected/unprovided attributes.
- UI: approved title/instructions plus bounded sections/summary layout and detail settings.

## Requirement-to-test traceability

| Stable requirement | Acceptance evidence |
|---|---|
| `ADV-INPUT-001` | `AC-ADV-INVALID`: invalid/missing input rejection |
| `ADV-DECISION-001` | `AC-ADV-ELIGIBLE`, `AC-ADV-INELIGIBLE`, `AC-ADV-BOUNDARY` |
| `ADV-DECISION-002` | `AC-ADV-PREREQ`, `AC-ADV-MULTIPLE` |
| `ADV-EXPLAIN-001` | `AC-ADV-EXPLAIN`: rule ID and actual unmet count |
| `ADV-RECOMMEND-001` | `AC-ADV-RECOMMEND`: action corresponds to each gap |
| `ADV-SAFETY-001` | `AC-ADV-CLAIMS`: synthetic disclaimer/no unsupported claim |
| `ADV-UI-001` | `AC-ADV-UI`: approved bounded choices |

Every acceptance criterion produces one exact-version result with Pass, Fail, or Not Yet Tested.
All ten deterministic Advisor criteria pass in the reference fixture suite.

## Participant and version behavior

Participants can create the explicitly labeled synthetic Advisor, inspect requirements and status,
run evaluation, enter structured inputs, inspect the five requested result areas, validate a test,
apply a bounded title/recommendation-style improvement, retest/re-evaluate, and approve. Applying an
improvement creates a new Working Version and clears prior participant and automated evidence.
Approval requires both current-version participant confirmation and all required criteria passing.
Prior Approved, Published, and Export snapshots remain immutable.

## Compromises and next boundary

The existing `Project` metadata and string configuration maps remain the persistence envelope, so
application-type-specific configuration is typed at the adapter boundary rather than in relational
columns. `M0Service` still hosts both participant workflows, although evaluator dispatch is neutral.
This is acceptable for the bounded test but should split into application-type workflow services
behind a shared lifecycle coordinator before a third application is implemented.

A third structurally different application can reasonably reuse specification dispatch,
traceability, evaluation reports, version invalidation, approval, serialization, and provenance
without another major redesign. It would still require its own typed spec, implementation,
fixtures/evaluator, and UI adapter. Recommended next step: extract workflow dispatch from
`M0Service` and prove durable Advisor snapshot round-tripping before adding any third type or
Advisor deployment/export runtime.
