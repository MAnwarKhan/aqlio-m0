# M0 Deployment Runbook

## Current phase

Phase 1 is a local deterministic foundation. It requires no database, object storage, OIDC, or managed-AI credential. Run it with `streamlit run streamlit_app.py`.

## Pilot topology (approved, not yet implemented)

- Application: Streamlit Community Cloud
- Identity: Streamlit native OIDC with Google
- Database: Railway PostgreSQL via SQLAlchemy 2.x/psycopg 3 and Alembic migrations
- Files: private Railway S3-compatible storage
- Managed AI: OpenAI behind Aqlio generation/embedding ports

## Secret handling

Configure pilot secrets through the hosting control plane. Never commit `.env`, `.streamlit/secrets.toml`, database URLs, OIDC secrets, storage credentials, provider keys, signed URLs, or user content.

## Pilot release gate

Before staging, verify clean installation, startup configuration, migrations, restart persistence, private defaults, clean-browser link access, revocation, deletion, backup/restore, rollback, redacted logs, allowances, and the deterministic end-to-end journey. Production integration is intentionally deferred beyond Phase 1.
