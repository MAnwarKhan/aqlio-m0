# Aqlio M0 — Ask My Documents

Aqlio M0 is a guided Streamlit prototype for non-technical participants to create, test, and publish a document-question-answering assistant. Phase 1 provides a deterministic foundation only; it intentionally makes no paid AI calls and needs no production credentials.

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

The default development configuration uses deterministic authentication and fake AI adapters. Never add real secrets to `.env.example` or commit `.env`/`.streamlit/secrets.toml`.

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

Streamlit UI remains thin. Domain rules do not import Streamlit or vendors. Authentication, persistence, storage, generation, embedding, clock, and ID behavior live behind ports. Phase 1 supplies deterministic in-memory/local adapters; approved production adapters arrive in later phases.

Participant-facing Deploy means freezing and publishing an immutable assistant version inside Aqlio—not provisioning infrastructure.
