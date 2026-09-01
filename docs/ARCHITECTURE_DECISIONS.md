# Architecture Decisions

## ADR-001 — Streamlit M0 precedes the broader platform

**Status:** Accepted  
**Decision:** Deliver one Ask My Documents journey in Python/Streamlit. Preserve modular boundaries without implementing the broader marketplace/platform.

## ADR-002 — Ports isolate domain and application logic

**Status:** Accepted  
**Decision:** UI depends on application/domain APIs. Authentication, persistence, storage, generation, embedding, clock, and ID behavior are ports implemented by adapters. Domain code imports only the standard library and domain-local modules.

## ADR-003 — Deterministic development mode

**Status:** Accepted  
**Decision:** Local development and standard tests use a deterministic identity, clock, IDs, generation, embeddings, storage, and repositories. No credential or paid call is required.

## ADR-004 — Pilot infrastructure

**Status:** Accepted  
**Decision:** Streamlit Community Cloud hosts the M0 app. Railway supplies PostgreSQL and private S3-compatible storage. SQLAlchemy 2.x, Alembic, and psycopg 3 form the persistence stack. Pilot identity uses Streamlit OIDC with Google.

## ADR-005 — Provider-neutral AI and bounded cost

**Status:** Accepted  
**Decision:** Generation and embedding use separate ports. OpenAI is the first managed adapter, not a domain dependency. Calls require authentication, authorization, allowance enforcement, bounded execution, normalized errors, and auditable usage.

## ADR-006 — Immutable publication and private sharing

**Status:** Accepted  
**Decision:** Participant Deploy freezes an immutable project/assistant version. Draft edits never mutate publications. Sharing defaults to private, link-only access uses an unguessable/revocable link, and M0 has no public directory.

See `M0_ARCHITECTURE_DECISIONS_2026-08-29.md` for the complete approved decision record.

## ADR-007 — Deterministic vertical slice uses in-memory adapters

**Status:** Accepted for Phase 2
**Decision:** The complete local journey uses authorization-aware application services over deterministic in-memory repository/storage adapters. Streamlit session state is transient only. These adapters must be replaced by approved PostgreSQL and private file-storage adapters before pilot use.

## ADR-008 — Version-scoped lexical retrieval before managed retrieval

**Status:** Accepted for Phase 2
**Decision:** Deterministic retrieval performs bounded lexical matching only over prepared chunks belonging to the authorized current project version. Likely operational instructions inside documents are excluded from candidates. Generation receives retrieved evidence or an empty context and must abstain.

## ADR-009 — Publications snapshot immutable participant-visible state

**Status:** Accepted
**Decision:** Deploy snapshots the project name, assistant configuration, prepared asset identifiers, and source chunks into a frozen publication. Sharing state is separate so it can change or be revoked without mutating the publication.

## ADR-010 — Durable state and transaction boundaries

**Status:** Accepted for Phase 3
**Decision:** SQLAlchemy repositories persist application state in PostgreSQL-compatible tables managed by Alembic. Multi-record commands use application-level transaction boundaries. Expected preparation and AI rejections commit their failure/usage evidence rather than rolling it back.

## ADR-011 — Private object storage and compensating cleanup

**Status:** Accepted for Phase 3
**Decision:** Uploaded bytes use server-generated workspace/project-scoped keys in private S3-compatible storage. Database metadata is authoritative. If metadata persistence fails after upload, the service attempts compensating object deletion; malformed or cross-project keys are rejected.

## ADR-012 — OIDC identity is not authorization

**Status:** Accepted for Phase 3
**Decision:** Streamlit validates Google OIDC. A stable provider/subject mapping identifies the user, while persisted membership, active state, ownership, and admin status authorize every server-side operation. A returning disabled user stays disabled.

## ADR-013 — Replaceable rate limiting

**Status:** Accepted for Phase 3
**Decision:** Upload, preparation, AI, and shared-link entry points use a rate-limit port. The Phase 3 implementation is process-local and suitable for the single-instance pilot; a shared backend is required before horizontal scaling.

## ADR-014 — Managed AI metadata stays provider-neutral

**Status:** Accepted for Phase 4
**Decision:** Generation and embedding results may carry generic usage metadata: provider/model identifiers, input/output units, estimated cost, latency, and retry count. SDK objects and raw exceptions stay inside adapters. Pricing is configuration, not domain policy.

## ADR-015 — Trusted retrieval owns citations

**Status:** Accepted for Phase 4
**Decision:** Managed output may select only chunk IDs included in the authorized retrieved context. Aqlio maps those IDs to trusted source metadata and rejects fabricated references. Empty evidence causes local abstention without a paid provider call.

## ADR-016 — Managed activation is an explicit release step

**Status:** Accepted for Phase 4
**Decision:** Fake mode remains the development/CI default. Managed mode fails closed without key and model configuration. Live tests are separately enabled and bounded by call and estimated-cost caps; adding adapters does not activate them.
