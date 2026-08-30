# Phase 5 Staging Validation Record

## Release identity

- Phase 4 checkpoint: `70b79a2`
- Required Alembic head: `20260829_0002`
- Initial staging AI mode: `fake`
- Managed activation: separate, explicit release action only

## Standard quality evidence

Run without production credentials or provider calls:

```bash
ruff format --check .
ruff check .
mypy app
python -m pytest
python -m pytest tests/evals
python -m pytest tests/e2e tests/integration tests/persistence
```

Local pilot configuration was verified to fail closed when database, object-storage, and OIDC settings were absent. Two independent clean databases migrated reproducibly from zero through `20260829_0002`; their 21-table schemas matched.

## Live validation matrix

### Credential-free validation

| Gate | Status | Evidence |
|---|---|---|
| Ruff format | PASSED | 52 files formatted |
| Ruff lint | PASSED | No findings |
| Mypy | PASSED | 28 source files |
| Full deterministic regression | PASSED | 58 passed; 1 credential-gated live test skipped |
| Evaluation suite | PASSED | 5 passed |
| E2E/integration/persistence | PASSED | 25 passed |
| Authorization/isolation and sharing/revocation | PASSED | 7 focused release-critical tests |
| Pilot fail-closed configuration | PASSED | Missing database/storage/OIDC categories rejected; no fallback |
| Clean migrations | PASSED | Two independent upgrades through `20260829_0002` |
| Schema reproducibility | PASSED | Matching 21-table schemas |
| Static secret scan | PASSED | No committed credential values; `.env.example` contains placeholders only |
| Logging/privacy design review | PASSED | Redaction tests and content-free provider usage/error records |
| Local Streamlit startup | PASSED | `/_stcore/health` returned `ok` |

### Live staging and managed AI

The following items require isolated staging services and must not be marked passed from local fakes.

| Gate | Status | Required evidence |
|---|---|---|
| Streamlit Community Cloud staging deployment | NOT RUN — EXTERNAL ENVIRONMENT REQUIRED | Staging URL and deployed `70b79a2` or later release commit |
| Railway PostgreSQL | NOT RUN — CREDENTIALS REQUIRED | Fresh migration, version query, full journey, restart reconstruction |
| Private S3-compatible storage | NOT RUN — CREDENTIALS REQUIRED | Private access, upload/get/delete, collision/isolation, denied-write check |
| Google OIDC | NOT RUN — CREDENTIALS REQUIRED | New login, repeated login, logout, stable subject, inactive-user denial |
| Two-identity authorization | NOT RUN — EXTERNAL ENVIRONMENT REQUIRED | Cross-user project/file/publish/revoke attempts denied |
| Fake-AI staging journey | NOT RUN — EXTERNAL ENVIRONMENT REQUIRED | Login through revocation in a clean browser |
| Backup/restore drill | NOT RUN — EXTERNAL ENVIRONMENT REQUIRED | Isolated restored database/object pair and relationship verification |
| Application rollback drill | NOT RUN — EXTERNAL ENVIRONMENT REQUIRED | Roll back code without database reset; verify persisted state |
| Managed embedding/generation | NOT RUN — CREDENTIALS REQUIRED | Capped live adapter calls and durable usage |
| Grounding/citation/injection | NOT RUN — CREDENTIALS REQUIRED | Four-call suite using non-sensitive corpus |
| Usage/cost reconciliation | NOT RUN — CREDENTIALS REQUIRED | Application rows and provider usage match within cap |
| Staging log/privacy review | NOT RUN — EXTERNAL ENVIRONMENT REQUIRED | Secret/content scan of real staging logs |
| Staging accessibility review | NOT RUN — EXTERNAL ENVIRONMENT REQUIRED | Keyboard, labels, feedback, readiness and sharing review |

## Safe staging order

1. Push the accepted checkpoints to the staging source branch only after confirming it cannot trigger an unintended production deployment.
2. Provision isolated Railway PostgreSQL and a private object bucket. Configure secrets only in Railway/Streamlit control planes.
3. Configure Google OIDC for the exact staging redirect URL and provide two approved test identities.
4. Set `APP_ENV=pilot`, durable adapters, Google OIDC, and `AQLIO_AI_MODE=fake`.
5. Run `alembic upgrade head` once from a controlled release job, then verify `20260829_0002`.
6. Complete infrastructure, authentication, authorization, happy-path, restart, clean-browser, backup/restore, rollback, privacy, and accessibility checks.
7. Only after every security gate passes, configure OpenAI and run `tests/live` with `LIVE_AI_TEST_MAX_CALLS=4` and a small explicit estimated-cost cap.
8. Reconcile application usage rows with provider usage. Managed activation remains a separate decision.

## Evidence capture rules

- Record timestamps, release commit, migration revision, staging service identifiers, and pass/fail outcomes.
- Never copy credentials, connection strings, OIDC tokens, signed URLs, prompts, documents, or answers into this file or logs.
- Record generation calls, embedding calls, total calls, estimated cost, cap, and provider-side reconciliation exactly.
- Any cross-user access, private publication exposure, mutable-draft leakage, revocation failure, pre-allowance provider call, fabricated citation, or secret leakage is a release blocker.

## Current decision

**NOT READY FOR SMALL PILOT.** The implementation is locally release-ready, but real staging infrastructure, identity, backup/restore, rollback, privacy, accessibility, and capped provider validation have not yet been executed.
