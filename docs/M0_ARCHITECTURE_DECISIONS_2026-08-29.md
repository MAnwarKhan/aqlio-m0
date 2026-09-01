# Aqlio M0 Architecture Decisions — 2026-08-29

This record resolves the Phase 0 blockers and authorizes implementation within the repository-defined **Ask My Documents** M0.

## Approved decisions

- **Scope:** Streamlit M0 is authoritative; the broader Aqlio MVP is future context only.
- **Architecture:** Python + Streamlit with separate UI, application, domain, ports, adapters, infrastructure, and configuration modules.
- **Participant deployment:** “Deploy” publishes an immutable assistant version; it does not provision infrastructure.
- **Pilot host:** Streamlit Community Cloud.
- **Development authentication:** deterministic identity behind `AuthPort`.
- **Pilot authentication:** Streamlit native OIDC with Google first; Aqlio owns authorization, membership, roles, activation, ownership, and admin permissions.
- **Tenancy:** user → individual workspace → projects, retaining workspace membership for future teams.
- **Persistence:** PostgreSQL hosted on Railway, SQLAlchemy 2.x, Alembic, and psycopg 3.
- **Object storage:** private Railway S3-compatible storage; PostgreSQL stores metadata, state, chunks, usage, and publications—not uploaded binaries.
- **Documents:** PDF, DOCX, and TXT; no OCR in M0; limits are configurable.
- **AI:** provider-neutral `GenerationPort` and `EmbeddingPort`; deterministic fakes for development/tests; OpenAI is the first managed provider, with models configured externally.
- **Retrieval:** no dedicated vector service; use a replaceable retrieval boundary and PostgreSQL-compatible storage when justified.
- **Security:** scope all access/retrieval to authorized workspace, project, version, and document set. Treat document text as untrusted reference content.
- **Answering:** answer from retrieved evidence with citations or clearly abstain.
- **Readiness:** project + prepared valid document + guided test + no blocking preparation error + explicit participant confirmation.
- **Sharing:** `PRIVATE`, `LINK_ONLY`, or `REVOKED`; link access is to an immutable publication and is revocable.
- **Cost:** authenticate → authorize → check allowance → call provider → record usage. No paid call may precede those gates.
- **Portfolio/admin:** persist deployment evidence; defer full portfolio UI. Keep protected operations minimal.

## Phase boundaries

Phase 1 builds the deterministic foundation without external credentials. Phase 2 builds the complete deterministic vertical slice. Phase 3 adds approved pilot persistence, OIDC, private object storage, and security controls. Phase 4 adds real extraction and managed OpenAI adapters behind ports. Phase 5 deploys/hardens the Streamlit Community Cloud pilot.

No further approval is required for implementation choices inside these boundaries.
