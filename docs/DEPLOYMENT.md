# M0 Deployment Runbook

## Current phase

Phase 4 is implemented but not activated. Development remains credential-free and uses fake AI by default. Pilot/staging can explicitly select managed generation and embeddings after the infrastructure and budget gates below pass.

## Pilot topology

- Application: Streamlit Community Cloud
- Identity: Streamlit native OIDC with Google
- Database: Railway PostgreSQL via SQLAlchemy 2.x/psycopg 3 and Alembic migrations
- Files: private Railway S3-compatible storage
- AI: deterministic fake adapters by default; optional managed OpenAI adapters behind provider-neutral ports

## Release procedure

1. Provision Railway PostgreSQL and a private S3-compatible bucket. Disable public bucket access.
2. Install `.[pilot]`, set the variables from `.env.example`, and use `APP_ENV=pilot`, `AQLIO_PERSISTENCE_MODE=sqlalchemy`, `AQLIO_STORAGE_MODE=s3`, `AQLIO_AUTH_MODE=oidc`, `OIDC_PROVIDER=google`, and initially `AQLIO_AI_MODE=fake`.
3. Configure Streamlit native OIDC in the Community Cloud secrets control plane with the Google client ID/secret, redirect URI, cookie secret, and provider metadata. Also provide the Aqlio OIDC settings required by fail-closed startup validation.
4. From a release job with database access, run `alembic upgrade head` before starting the new application version.
5. Start with `streamlit run streamlit_app.py`, sign in as a participant and an `ADMIN_EMAILS` operator, and execute the pilot release gate below.

## Controlled managed-AI activation

1. Keep the deployed pilot in fake mode while validating migrations, authorization, storage, sharing, and rollback.
2. Configure the API key and explicit generation/embedding model identifiers only through Streamlit secrets. Set timeout, retry limit, and replaceable per-million pricing metadata from `.env.example`.
3. In an isolated staging environment, enable `LIVE_AI_TESTS_ENABLED=true` with `LIVE_AI_TEST_MAX_CALLS=4` and a small nonzero cost cap. Run only `python -m pytest tests/live -m live_ai`.
4. Review grounded answer, abstention, injection resistance, trusted citations, durable usage, retry counts, latency, and estimated cost. Disable the live-test flag afterward.
5. Activate `AQLIO_AI_MODE=managed` as a separate release change. Missing key/model settings fail startup; the application never falls back silently to fake mode.

Provider calls use bounded SDK timeouts and adapter-owned bounded retries. Only normalized error categories reach application state. Responses requests disable provider-side response storage, and operational data excludes raw prompts, document content, answers, credentials, and provider exception bodies.

Do not run migrations concurrently from every web process. Back up the database and bucket before schema changes. A database restore and its matching object snapshot must be restored together.

## Data lifecycle and recovery

- Publications are immutable. Sharing revocation changes only the share-link record and takes effect immediately.
- Phase 3 does not expose hard deletion in participant or operator UI. Treat removal requests as an operational procedure: revoke access, archive/export evidence, delete object keys scoped to the confirmed workspace/project, then remove relational rows in a controlled transaction.
- Restore into an isolated environment first, run migrations, verify row/object counts and a representative publication, then promote the restored services.
- Rollback application code only to a version compatible with the migrated schema; schema downgrade is not an automatic release step.

## Secret handling

Configure pilot secrets through the hosting control plane. Never commit `.env`, `.streamlit/secrets.toml`, database URLs, OIDC secrets, storage credentials, provider keys, signed URLs, or user content.

## Minimum external prerequisites

### Railway PostgreSQL

- An isolated staging PostgreSQL service and operator access capable of setting its connection URL in Streamlit secrets.
- Network access from the migration runner and Streamlit Community Cloud.
- Permission to run `alembic upgrade head`, inspect the migration revision, create a backup/snapshot, and restore into a separate target.

### Private object storage

- An isolated S3-compatible endpoint, private bucket, region if required, and scoped access-key credentials configured in Streamlit secrets.
- Permission for only the required put/get/delete operations and access to confirm public browsing is disabled.
- A separate or safely namespaced restore target for the backup/restore drill.

### Google OIDC

- A Google OAuth/OIDC client configured for the exact Streamlit staging redirect URI.
- Client ID and secret configured through Streamlit native authentication secrets, plus a strong cookie secret.
- Two approved staging Google identities, with one optional admin email, for first-login, repeat-login, logout, inactive-user, and cross-user authorization checks.

### Streamlit Community Cloud

- Access to deploy the GitHub repository to an isolated staging application without triggering an unintended production release.
- Repository/branch selection, staging URL, secret-management access, application logs, restart/redeploy control, and rollback to a known commit.
- Confirmation of the staging source branch before pushing the four local accepted checkpoints currently ahead of `origin/main`.

### OpenAI

- A staging-scoped API key stored only in Streamlit/platform secrets and explicit generation/embedding model identifiers.
- Reviewed per-million pricing metadata, `LIVE_AI_TEST_MAX_CALLS=4`, and a small explicit `LIVE_AI_TEST_MAX_ESTIMATED_COST`.
- Permission to inspect provider-side usage for reconciliation. Do not enable managed mode until all fake-AI infrastructure/security gates pass.

## Pilot release gate

Before staging, verify clean installation, fail-closed startup configuration, migrations, restart persistence, private defaults, clean-browser link access, revocation, the documented deletion procedure, backup/restore, rollback compatibility, redacted logs, allowances, rate limits, admin authorization, and the deterministic end-to-end journey.

Standard tests use SQLite, a fake S3 client, and fake/injected AI clients and require no credentials. Live PostgreSQL/S3/OIDC/AI checks are deliberately opt-in and must run only in an isolated pilot environment with temporary credentials and explicit budgets.
