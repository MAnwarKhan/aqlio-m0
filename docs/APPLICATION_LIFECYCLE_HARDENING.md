# Application lifecycle architecture hardening — 2026-09-06

## Persistence and reconstruction

An immutable `ApprovedVersionSnapshot` now includes `ParticipantValidationEvidence` for the exact
Working Version: validation record ID, version ID, participant ID, privacy-safe input summary,
validation timestamp, and confirmed outcome. The SQL approved-version row stores that evidence
beside the already snapshotted application type, behavior/UI configuration, typed Behavioral
Specification, exact evaluation report, project/version IDs, and approval timestamp.

Reconstruction dispatches the Behavioral Specification by its persisted schema and checks that the
schema's registered application type equals the row's persisted application type. Unknown
application types, unknown schemas, and mismatched type/schema pairs raise errors. They are never
treated as Ask My Documents. Existing approved rows remain compatible because the new evidence
column is nullable; legacy rows reconstruct with no participant-evidence snapshot rather than
inventing one.

New Working Versions persist both `template` and `behavioral_schema` in their immutable version
configuration. The lifecycle coordinator compares those values with the project's persisted type
and the adapter-produced typed specification. Older versions without a schema hint remain readable.

## Service boundaries

`LifecycleCoordinator` owns reusable exact-version mechanics:

- resolve application type and typed specification through the registry;
- run the registered evaluator and persist its exact-version report;
- record participant validation and trigger fresh evaluation;
- invalidate test/evaluation/readiness evidence after improvement;
- approve only the validated, passing exact version;
- construct immutable provenance.

`AdvisorWorkflowService` owns only Advisor definition, build configuration, structured deterministic
test execution, and bounded improvement. It has no document ingestion, retrieval, grounding,
citation, or document-answer dependency. `M0Service` remains the Ask My Documents workflow façade
and exposes compatibility delegates to the coordinator and Advisor service; it no longer implements
Advisor rules or Advisor version-building details.

Ask My Documents runtime entry points reject Advisor projects, and Advisor workflow entry points
reject Ask My Documents projects. Application type dispatch is fail-closed.

## Migration

Migration `20260906_0007` additively adds nullable JSON `participant_validation` to
`approved_versions`. New approvals require durable Guided Test evidence for their exact version and
snapshot it. Older immutable approvals are not rewritten or reinterpreted.

## Extension boundary

A deliberate future application type should require a typed specification, its workflow/runtime,
evaluator/fixtures, UI adapter, and one registry registration. The shared lifecycle should not need
a new conditional branch. Remaining coupling is that the historical `M0Service` still implements
the sizeable Ask My Documents workflow and supplies compatibility delegates; splitting that façade
is cleanup, not a prerequisite for testing another registered type.
