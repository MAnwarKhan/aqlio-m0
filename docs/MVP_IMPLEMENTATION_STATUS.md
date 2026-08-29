# Aqlio M0/MVP Implementation Status

**Audit date:** 2026-08-29  
**Repository:** `MAnwarKhan/aqlio-m0`  
**Branch audited:** `main` at `697ecea`  
**Current phase:** Phase 1 — deterministic foundation complete

## Executive summary

The repository began as a specification-only repository. Phase 1 now provides a runnable, credential-free Python/Streamlit foundation with framework-independent domain rules, replaceable ports, deterministic development adapters, typed configuration, structured redaction, tests, CI, and setup/deployment documentation.

The repository-level instructions define a narrower M0 than the broad MVP master prompt: one Streamlit-based **Ask My Documents** journey for a non-technical participant. Those instructions make the first three M0 documents authoritative and treat the broader MVP specification as future context. The safest next implementation is therefore the smallest deterministic M0 vertical slice, while preserving provider and persistence interfaces that can later support the broader modular-monolith MVP.

The Ask My Documents product journey, durable PostgreSQL/object-storage persistence, OIDC, and managed AI remain later phases by design.

## Repository inventory

| Path | Audit result |
| --- | --- |
| `streamlit_app.py` | Runnable thin Streamlit entry point |
| `app/` | Domain, ports, deterministic adapters, application composition, configuration, infrastructure, and UI foundation |
| `AGENTS.md` | Valid UTF-8 Markdown; original preserved under `docs/archive/` |
| `docs/Aqlio_M0_First_Useful_Deployment_Implementation_Package v1.0.docx` | Detailed M0 product/delivery authority |
| `docs/Aqlio_M0_UX_UI_Screen_Specification v1.0.docx` | Participant-visible flow/copy authority |
| `docs/Aqlio_M0_Streamlit_Prototype_Technical_Specification v1.0.docx` | Streamlit prototype architecture authority |
| `docs/Aqlio_MVP_Implementation_Specification_v2.0.doc` | Broader MVP/future context; legacy `.doc` format |

The filenames referenced inside `AGENTS.md` do not exactly match the committed filenames: the committed M0 files include ` v1.0`, and the broader specification is `.doc`, not `.docx`. This should be corrected during foundation setup so instructions are portable and machine-readable.

## COMPLETE

- Product direction and M0 outcome are documented.
- The primary M0 journey is defined: enter workspace → create project → choose Ask My Documents → add documents → test → review readiness → deploy/publish → open assistant.
- Participant-facing language and prohibited infrastructure terminology are documented.
- Architecture boundaries are specified for UI, application services, domain rules, ports/interfaces, and external adapters.
- Privacy, security, accessibility, cost-control, testing, and release-gate expectations are documented.
- Deterministic fake providers are explicitly approved for automated tests.
- Git repository and `main` branch exist with a clean working tree before this audit document was added.
- Python 3.12 project metadata, pinned runtime/development dependencies, environment example, ignore rules, README, Streamlit configuration, and CI quality workflow exist.
- Core project lifecycle and approved readiness rules are framework-independent and tested.
- Authentication, persistence, storage, generation, embedding, clock, and ID boundaries are defined as typed ports.
- Deterministic identity, IDs, clock, fake generation/embeddings, in-memory storage, and isolation-aware project repository are implemented.
- Development startup requires no production credentials and makes no paid AI calls.
- Structured logging redacts sensitive fields by default.

## PARTIAL

- The Streamlit UI is intentionally a minimal Phase 1 welcome screen; project creation and journey screens remain Phase 2.
- Persistence/storage ports exist, but current adapters are deterministic and in-memory only.
- Source documents describe PostgreSQL, private object storage, provider adapters, usage limits, immutable versions, and sharing, but none are implemented.
- The master prompt requests a modular monolith and Railway-ready MVP, while repository instructions prescribe a Streamlit Community Cloud M0 prototype first. The proposed module boundaries can support both, but the immediate deployment target needs an explicit phase boundary.
- Organization, portfolio, verification, administration, BYO-provider credentials, and broader project types are specified in the master MVP but intentionally outside or beyond the repository's initial M0 journey.

## MISSING

### Foundation and developer experience

- Lockfile and automated dependency/security scanning beyond pinned dependency installation.
- Pilot health diagnostics and operational alerting.

### Identity, authorization, and tenancy

- Registration, login, logout, secure sessions, user activation state, and server-side roles.
- Automatic individual workspace creation and membership.
- Server-side project/document/publication ownership checks and horizontal-isolation tests.
- Staff/admin authorization for protected diagnostics.

### Domain and persistence

- Domain entities, status enums, transition rules, immutable versions, audit/lifecycle events, and readiness rules.
- Repository/unit-of-work interfaces and implementations.
- PostgreSQL schema, typed persistence layer, migrations, indexes, uniqueness constraints, and cascade/deletion policy.
- Required M0 records for users/workspaces/memberships, projects/versions, assets/ingestion jobs/chunks, chats/runs, usage/allowances, publications/shares, and audit events.
- Development seed data and deterministic IDs/clocks for testing.

### Ask My Documents workflow

- Workspace, project creation, single-template selection, guided onboarding, and navigation guards.
- Private upload, server-side type/size validation, safe filenames, project-scoped storage, extraction, chunking, embedding, and idempotent preparation.
- Retrieval constrained to the authorized project/version.
- Prompt-injection defenses, grounded answers, visible citations, honest abstention, and guided test questions.
- Readiness confirmation, deployment/publishing state machine, immutable published assistant version, link visibility, revocation, and clean-session access.
- Portfolio suggestion/evidence flow.

### AI gateway, usage, and cost

- Provider-neutral generation/embedding contracts and normalized responses/errors.
- Deterministic fake AI and embedding adapters.
- Managed provider adapter, server-controlled routing, bounded fallback, timeout, and retry behavior.
- Auditable usage ledger, configurable allowances/budgets, pre-call enforcement, estimated cost metadata, and user-facing usage screen.

### Operations and administration

- Minimal protected operational views for failures, aggregate usage, providers/models, and allowance configuration.
- Rate limiting, abuse controls, correlation IDs, privacy-safe analytics, backup/restore, deletion/revocation, and rollback drills.
- Streamlit Community Cloud staging configuration and/or Railway production deployment configuration.

### Verification

- Unit, integration, evaluation, end-to-end, authorization, privacy, accessibility, and failure-recovery tests.
- Fixture corpus and citation-quality/abstention evaluation thresholds.
- A complete happy-path acceptance test without paid external calls.

## BLOCKED

No approved architecture decision is blocked. The Aqlio M0 Architecture Decision Addendum dated 2026-08-29 authorizes Streamlit native OIDC with Google; Railway PostgreSQL using SQLAlchemy 2.x, Alembic, and psycopg 3; private Railway S3-compatible storage; provider-neutral AI ports with deterministic fakes and OpenAI as the first managed adapter; Streamlit Community Cloud for the M0 pilot; and Railway for the later broader MVP.

External service credentials and provisioned pilot resources will be required only when their approved implementation phases begin. They do not block Phase 1 or Phase 2.

## OUT OF SCOPE

For the repository-defined M0 unless explicitly approved:

- Participant-facing GitHub, Railway, repositories, branches, commits, API keys, environment variables, model selection, embeddings, vector-database, container, or deployment-pipeline controls.
- Multiple solution templates or separate engines for applications, agents, workflows, automations, and RAG products.
- Bring-your-own provider credentials and participant-selected providers/models.
- Payments, subscriptions, marketplace, recruiting, payroll, native mobile apps, multi-agent systems, arbitrary tools/plugins, enterprise administration, complex workflow builders, and public sharing by default.
- Per-user repository/service/container provisioning.
- Microservices, Kubernetes, service mesh, event streaming, and other infrastructure not justified by the M0 journey.

## Recommended implementation plan

### Phase 1 — deterministic foundation

1. Convert `AGENTS.md` into real Markdown and correct authoritative-document links without changing its meaning.
2. Add the Python/Streamlit project scaffold, minimal pinned dependencies, configuration validation, `.gitignore`, `.env.example`, README, and quality-tool configuration.
3. Create domain models and transition/readiness rules independent of Streamlit.
4. Define repository, storage, AI/embedding, clock, and ID interfaces; implement local development repositories and deterministic fakes only.
5. Add unit tests and make `pytest`, `ruff`, formatting, and `mypy` checks executable.

**Checkpoint:** fresh setup runs a deterministic app and all quality checks pass without credentials or paid calls.

### Phase 2 — smallest complete M0 vertical slice

1. Implement a development identity/workspace boundary behind an authentication interface.
2. Build project creation and the single Ask My Documents template.
3. Add safe PDF/DOCX/TXT validation and deterministic fixture ingestion.
4. Implement guided preview with fake grounded answers, citations, abstention, readiness, publication, private/link visibility, and revocation.
5. Persist lifecycle/audit and usage events through interfaces and cover isolation/state transitions with tests.

**Checkpoint:** the canonical journey works end to end locally with deterministic data and no external services.

### Phase 3 — pilot persistence and security

After approval of authentication, PostgreSQL schema, and object-storage choices:

1. Add additive migrations and repository implementations.
2. Add managed authentication/session enforcement and server-side roles.
3. Add private object storage, deletion, signed/server-side access, and restart-persistence tests.
4. Add rate limits, allowances/budgets, redacted logs, privacy-safe analytics, and protected operations views.

### Phase 4 — real document intelligence

After approval of the production provider:

1. Implement extraction/chunking and provider-neutral embedding/generation adapters.
2. Add project/version-scoped retrieval, citation mapping, prompt-injection policy, fallback, usage reconciliation, and quality evaluations.
3. Keep live-provider tests opt-in and budget-bounded.

### Phase 5 — staging and release hardening

1. Implement Community Cloud staging for repository-defined M0, documenting Railway as the later production path unless the deployment decision is changed.
2. Run clean-install, restart, clean-browser sharing, revocation, deletion, backup/restore, rollback, security, privacy, accessibility, cost, and end-to-end checks.
3. Update implementation log, architecture decisions, status, and deployment runbook at every checkpoint.

## Migration outline

No migration can be generated until the initial schema and persistence choice are approved. The first migration should be additive and establish identity/workspace, project/version/lifecycle, document/ingestion, publication/share, AI run/usage/allowance, and audit records with UUID primary keys, timestamps, ownership foreign keys, uniqueness constraints, project/workspace indexes, and deliberately reviewed deletion behavior. Document chunks and flexible operational metadata may use structured/JSON fields only where relational columns are not appropriate; document binaries must remain outside PostgreSQL.

## Highest-priority security concerns

1. Cross-project document or retrieval leakage.
2. Public-link access accidentally exposing drafts or mutable/private content.
3. Raw documents, prompts, answers, secrets, or provider errors entering logs/analytics.
4. Unsafe file parsing, filenames, type spoofing, oversized uploads, and malicious document instructions.
5. Provider calls occurring before authorization and allowance enforcement.
6. Streamlit cache/session state being treated as authoritative or globally caching user content.
7. Unbounded retries, duplicate ingestion/publication, and cost amplification.
8. Admin/diagnostic functions protected only by UI visibility rather than server-side authorization.

## Phase 0 conclusion

Phase 0 is complete and its architecture blockers are resolved. Phase 1 has turned the repository into a runnable deterministic foundation. The next action is Phase 2: implement the smallest complete local Ask My Documents journey on the existing ports, keeping it credential-free and horizontally isolated.
