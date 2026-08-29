# Implementation Log

## Phase 0 — Repository audit

**Status:** Complete  
**Implemented:** Audited the specification-only repository and classified all M0/MVP capabilities.  
**Files changed:** `docs/MVP_IMPLEMENTATION_STATUS.md`  
**Database changes:** None.  
**Tests added:** None.  
**Known issues:** Repository was not runnable; architecture decisions were initially unresolved.  
**Deferred items:** All implementation.  
**Next phase:** Deterministic foundation.

## Phase 1 — Deterministic foundation

**Status:** Complete.  
**Implemented:** Real Markdown instructions with archived original; approved ADRs; Python/Streamlit scaffold; typed configuration and fail-closed pilot validation; domain project lifecycle/readiness rules; authentication, repository, storage, generation, embedding, clock, and ID ports; deterministic adapters; structured redaction; minimal participant-safe home screen; developer setup; CI and tests.  
**Files changed:** Application modules, tests, project/tool configuration, CI, README, environment example, Streamlit configuration, and docs.  
**Database changes:** None. Approved SQLAlchemy/Alembic/PostgreSQL implementation remains Phase 3.  
**Tests added:** Configuration, readiness/lifecycle, deterministic identity/IDs/embeddings, citations/abstention, repository/storage isolation, log redaction, and an evaluation test.  
**Known issues:** Product journey screens and durable persistence are intentionally not part of Phase 1.  
**Deferred items:** Phase 2 deterministic vertical slice; Phase 3 pilot infrastructure; Phase 4 managed AI.  
**Next phase:** Create the smallest complete deterministic Ask My Documents journey.

### Quality gate

- `ruff format --check .` — passed (22 files)
- `ruff check .` — passed
- `mypy app` — passed (16 source files)
- `python -m pytest` — passed (14 tests)
- `python -m pytest tests/evals` — passed (1 evaluation)
- Streamlit startup and `/_stcore/health` smoke test — passed (`ok`)
- Production credentials/paid provider calls — none used

## Phase 2 — Deterministic Ask My Documents vertical slice

**Status:** Complete.
**Implemented:** Automatic individual workspace/membership; participant project creation; PDF/DOCX/TXT validation; safe storage names; deterministic private storage; real local extraction; normalization/chunking/fake embeddings; version-scoped retrieval; grounded fake generation with citations/abstention; prompt-injection candidate filtering; guided tests; usage/allowance enforcement; readiness confirmation; immutable private publication; link-only sharing; clean-session access; revocation; lifecycle/audit records; participant-safe Streamlit journey.
**Files changed:** Domain/port models, deterministic adapters, M0 service, document processing, UI, fixtures, tests, dependencies, README, and architecture/status documentation.
**Database changes:** None. Phase 2 deliberately uses replaceable process-local adapters.
**Tests added:** Upload/type/size/extraction failures; idempotent preparation; lifecycle/readiness; grounded citations/abstention; malicious instructions; allowances before generation; horizontal isolation; immutable publication; private/link-only/revoked access; full deterministic journey; participant-language guard.
**Known issues:** State and uploaded bytes reset when the local process restarts. PDF files without extractable text are rejected; OCR is out of scope. Deterministic lexical retrieval is intentionally small-corpus behavior.
**Deferred items:** PostgreSQL/SQLAlchemy/Alembic, OIDC, private pilot file storage, rate limiting, durable allowances/audit data, managed AI, and operations views.
**Next phase:** Implement approved durable pilot infrastructure in security-first dependency order.

### Quality gate

- `ruff format --check .` — passed (33 files)
- `ruff check .` — passed
- `mypy app` — passed (19 source files)
- `python -m pytest` — passed (33 tests)
- `python -m pytest tests/evals` — passed (4 evaluations)
- `python -m pytest tests/e2e tests/integration` — passed (15 tests)
- Streamlit startup and `/_stcore/health` — passed (`ok`)
- Horizontal authorization/isolation — passed
- Publication privacy/immutability/sharing/revocation — passed
- Production credentials, paid AI calls, and external runtime services — none used

## Phase 3 — Durable pilot infrastructure

**Status:** Complete and commit-ready.
**Implemented:** Alembic-managed SQLAlchemy schema/repository; durable workspaces, versions, assets, chunks, usage, allowances, lifecycle/audit evidence, publications, and sharing; private local/S3-compatible storage; restart-safe reconstruction; Streamlit Google OIDC mapping; persisted authorization; protected operator snapshot/allowance control; entry-point rate limits; fail-closed pilot composition and deployment procedures.
**Database changes:** Initial M0 schema migration covering identity, authorization, project/document lifecycle, AI evidence, publication/sharing, and operations records.
**Tests added:** Fresh migration, transaction rollback, full restart reconstruction, post-restart revocation, private storage isolation, fake S3 behavior, OIDC claim mapping, disabled-user preservation, admin-only operations, and rate limiting.
**Known issues:** Standard CI validates PostgreSQL-compatible behavior through SQLite and S3 behavior through a fake client; live Railway/OIDC validation needs isolated external credentials. The in-memory rate limiter assumes one application instance. Hard deletion remains an operator runbook procedure rather than product UI.
**Deferred items:** Managed OpenAI generation/embedding, provider error policy/evals, and multi-instance shared rate limiting.
**Next phase:** Add managed AI in the approved Phase 4 security/cost/evaluation sequence.
