# M0 Deployment Runbook

## Current phase

Phase 3 is implemented. Development remains credential-free and in-memory by default. Pilot mode uses durable PostgreSQL, private S3-compatible storage, and Google OIDC while retaining fake AI until Phase 4.

## Pilot topology

- Application: Streamlit Community Cloud
- Identity: Streamlit native OIDC with Google
- Database: Railway PostgreSQL via SQLAlchemy 2.x/psycopg 3 and Alembic migrations
- Files: private Railway S3-compatible storage
- AI for Phase 3: deterministic fake generation and embeddings behind provider-neutral ports

## Release procedure

1. Provision Railway PostgreSQL and a private S3-compatible bucket. Disable public bucket access.
2. Install `.[pilot]`, set the variables from `.env.example`, and use `APP_ENV=pilot`, `AQLIO_PERSISTENCE_MODE=sqlalchemy`, `AQLIO_STORAGE_MODE=s3`, `AQLIO_AUTH_MODE=oidc`, `OIDC_PROVIDER=google`, and `AQLIO_AI_MODE=fake`.
3. Configure Streamlit native OIDC in the Community Cloud secrets control plane with the Google client ID/secret, redirect URI, cookie secret, and provider metadata. Also provide the Aqlio OIDC settings required by fail-closed startup validation.
4. From a release job with database access, run `alembic upgrade head` before starting the new application version.
5. Start with `streamlit run streamlit_app.py`, sign in as a participant and an `ADMIN_EMAILS` operator, and execute the pilot release gate below.

Do not run migrations concurrently from every web process. Back up the database and bucket before schema changes. A database restore and its matching object snapshot must be restored together.

## Data lifecycle and recovery

- Publications are immutable. Sharing revocation changes only the share-link record and takes effect immediately.
- Phase 3 does not expose hard deletion in participant or operator UI. Treat removal requests as an operational procedure: revoke access, archive/export evidence, delete object keys scoped to the confirmed workspace/project, then remove relational rows in a controlled transaction.
- Restore into an isolated environment first, run migrations, verify row/object counts and a representative publication, then promote the restored services.
- Rollback application code only to a version compatible with the migrated schema; schema downgrade is not an automatic release step.

## Secret handling

Configure pilot secrets through the hosting control plane. Never commit `.env`, `.streamlit/secrets.toml`, database URLs, OIDC secrets, storage credentials, provider keys, signed URLs, or user content.

## Pilot release gate

Before staging, verify clean installation, fail-closed startup configuration, migrations, restart persistence, private defaults, clean-browser link access, revocation, the documented deletion procedure, backup/restore, rollback compatibility, redacted logs, allowances, rate limits, admin authorization, and the deterministic end-to-end journey.

Standard tests use SQLite and a fake S3 client and require no credentials. Live PostgreSQL/S3/OIDC checks are deliberately opt-in and must run only in an isolated pilot environment with temporary credentials.
