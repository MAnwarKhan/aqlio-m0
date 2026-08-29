# Aqlio M0 — Ask My Documents

Aqlio M0 is a guided Streamlit prototype for non-technical participants to create, test, publish, and share a document-question-answering assistant. Phase 2 provides the complete deterministic journey; it intentionally makes no paid AI calls and needs no production credentials.

## Requirements

- Python 3.12
- Git

## Fresh setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
streamlit run streamlit_app.py
```

The default development configuration uses deterministic authentication, local in-memory repositories/storage, and fake AI adapters. Never add real secrets to `.env.example` or commit `.env`/`.streamlit/secrets.toml`.

## Deterministic journey

1. Enter with the development identity and resolve an individual workspace.
2. Create an Ask My Documents project.
3. Add and prepare a PDF, DOCX, or TXT document.
4. Test a grounded answer and inspect its source citation.
5. Confirm readiness and deploy an immutable private publication.
6. Open the assistant, explicitly enable link sharing, and stop sharing when desired.

All authoritative state flows through application/domain/repository boundaries. Streamlit session state holds only transient navigation and display conveniences. Restart persistence arrives with approved Phase 3 PostgreSQL and private file-storage adapters.

## Quality checks

```bash
ruff format --check .
ruff check .
mypy app
python -m pytest
python -m pytest tests/evals
```

## Configuration

Configuration uses environment variables. Development defaults are safe and credential-free. Pilot mode fails closed unless database, OIDC, private object storage, and managed-AI settings are present. See `.env.example` and `docs/DEPLOYMENT.md`.

## Architecture

Streamlit UI remains thin. Domain rules do not import Streamlit or vendors. Authentication, persistence, storage, generation, embedding, clock, and ID behavior live behind ports. Phase 2 uses deterministic in-memory/local adapters and project/version-scoped retrieval; approved production adapters arrive in later phases.

Participant-facing Deploy means freezing and publishing an immutable assistant version inside Aqlio—not provisioning infrastructure.
