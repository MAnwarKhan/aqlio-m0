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
