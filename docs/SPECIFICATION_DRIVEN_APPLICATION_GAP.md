# Specification Driven Application Development and Evaluation Gap

## Current conclusion

Aqlio now proves the first specification-driven architecture for Ask My Documents. Each Working
Version exposes a typed Behavioral Specification with stable requirement and acceptance-criterion
identifiers. A deterministic evaluator records Pass, Fail, or Not Yet Tested against the exact
project version. Required criteria and a participant-confirmed successful interaction both gate
new approvals. Approved snapshots and future export manifests preserve the contract and report.

This is deliberately a bounded proof, not a complete specification-driven application platform.

## Material gaps

- Ask My Documents requirements and acceptance cases are derived from a trusted template contract.
  Participants cannot yet add a new typed capability or author safe semantic assertions.
- Deterministic conformance cases prove the shared implementation contract and structured UI
  configuration. They do not prove that every participant document contains adequate, accurate, or
  representative content for the intended users.
- A participant-confirmed successful interaction remains required, but broader user acceptance is
  not yet represented as a structured test plan or coverage target.
- Retrieval and generation metrics are implementation checks. They do not by themselves establish
  that the output satisfied the user's task. Evaluation needs question-level semantic assertions.
- Improvements create a new version and invalidate the prior evaluation, but Aqlio does not yet
  compute a human-readable specification diff or select a risk-based subset before the full
  regression run.
- Export generation renders a fixed trusted application template with approved configuration. It
  does not compile an arbitrary behavioral specification into an application, which remains
  intentionally outside M0.

## Implemented lifecycle

`User Intent → Typed Ask My Documents Behavioral Specification → Derived Acceptance Criteria →`
`Deterministic Evaluation → Participant Validation → Improvement → New Version Regression`

Managed-provider semantic fidelity remains explicitly Not Yet Tested during the standard fake-mode
evaluation. Immutable artifacts created before this architecture remain readable and unchanged;
new approvals and exports include the additional provenance.

## Recommended next architectural phase

The next phase should validate whether this contract mechanism generalizes to a second,
structurally different reference application before any arbitrary generation work:

1. Define one typed contract with inputs, outputs, safety rules, and observable behavior that does
   not reduce to document question answering.
2. Derive its acceptance cases through the same requirement-to-criterion mechanism.
3. Introduce a template-neutral evaluator interface while retaining trusted implementations per
   application type.
4. Prove versioning, participant evaluation, improvement, approval, publication, and export
   provenance without weakening Ask My Documents regressions.

The phase should not infer unlimited functionality from prose or claim success because retrieval
returned related evidence. Its first quality gate should prove the full chain:

`User Intent → Behavioral Application Specification → Acceptance Tests → Implementation →`
`Automated Evaluation → User Validation → Improvement → Regression Testing`

Arbitrary code generation and user-authored executable tests should remain out of scope until a
second trusted reference application proves that the architecture is genuinely structural rather
than Ask My Documents terminology wrapped in generic names.
