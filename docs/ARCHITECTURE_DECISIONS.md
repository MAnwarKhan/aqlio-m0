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
