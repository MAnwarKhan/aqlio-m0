# Aqlio M0 — Ask My Documents

Aqlio M0 is a guided Streamlit prototype for non-technical participants to create, test, publish, and share a document-question-answering assistant. Phase 4 adds optional managed document intelligence while preserving deterministic, credential-free development and CI.

## Requirements

- Python 3.12
- Git

## Fresh setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,pilot]'
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

All authoritative state flows through application/domain/repository boundaries. Streamlit session state holds only transient navigation and display conveniences. SQLAlchemy/Alembic and private local or S3-compatible storage provide restart-safe pilot state.

## Quality checks

```bash
ruff format --check .
ruff check .
mypy app
python -m pytest
python -m pytest tests/evals
```

## Configuration

Configuration uses environment variables. Development defaults are safe and credential-free. Pilot mode fails closed unless database, OIDC, and private object-storage settings are present. Managed-AI settings are required only when managed AI is selected. See `.env.example` and `docs/DEPLOYMENT.md`.

## Architecture

Streamlit UI remains thin. Domain rules do not import Streamlit or vendors. Authentication, persistence, storage, generation, embedding, clock, ID, and rate-limit behavior live behind ports. Managed OpenAI generation and embedding are configuration-selected adapters; fake adapters remain the default and are never silently substituted in managed mode.

Managed mode requires `OPENAI_API_KEY`, `OPENAI_GENERATION_MODEL`, and `OPENAI_EMBEDDING_MODEL`. Pricing inputs are configuration metadata rather than embedded commercial assumptions. Live tests are disabled unless explicitly enabled and are protected by call and estimated-cost caps.

Participant-facing Deploy means freezing and publishing an immutable assistant version inside Aqlio—not provisioning infrastructure.
