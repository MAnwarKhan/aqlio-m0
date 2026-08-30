# Aqlio M0 — Turn ideas into working AI solutions

Aqlio guides nontechnical participants from an idea through definition, building, testing,
improving, running, and optional Aqlio-hosted publication. **Ask My Documents is the only
implemented solution template**, not the permanent platform boundary. Multiple projects
are independently saved through existing persistence interfaces.

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
2. Describe an idea; optionally evaluate it, then define a small first solution.
3. Start building with the document-assistant template. Selecting PDF, DOCX, or TXT files
   automatically adds and prepares them; failures show a retry action.
4. Test answers with sources. Improve answer length or add better source documents and retest.
5. Run the working application inside Aqlio. Deployment is optional and private by default.
6. Deploy a stable version in one action; explicitly enable sharing and revoke it when desired.
7. Return through My Projects or start another independent project.

All authoritative state flows through application/domain/repository boundaries. Streamlit session
state holds only transient navigation, upload-attempt suppression, and display conveniences.
**The default in-memory, shared-development-identity smoke environment is not durable or
multi-user pilot-ready.** It must use sample data only. Restart persistence is tested locally
through SQLAlchemy and private local storage; live PostgreSQL/S3/OIDC validation remains pending.

See `docs/PRODUCT_JOURNEY_REVISION.md` for scope, regression evidence, migration, and smoke checks.

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
