# AGENTS.md — Aqlio M0

## Project purpose

Build and test **Aqlio M0 — Turn ideas into working AI solutions**. The platform journey is
Idea → optional Evaluate → Define → Build → Test → Improve → Run → optional Deploy.
**Ask My Documents remains the only implemented template**, not the platform boundary.
The user-approved product revision is recorded in `docs/PRODUCT_JOURNEY_REVISION.md` and
supersedes narrower journey framing below/in the original documents, not their safety rules.

Optimize for the simplest successful user experience, not the largest feature set.

## Authoritative documents

Read these documents before significant product or architecture decisions:

1. [`docs/Aqlio_M0_First_Useful_Deployment_Implementation_Package v1.0.docx`](docs/Aqlio_M0_First_Useful_Deployment_Implementation_Package%20v1.0.docx)
2. [`docs/Aqlio_M0_UX_UI_Screen_Specification v1.0.docx`](docs/Aqlio_M0_UX_UI_Screen_Specification%20v1.0.docx)
3. [`docs/Aqlio_M0_Streamlit_Prototype_Technical_Specification v1.0.docx`](docs/Aqlio_M0_Streamlit_Prototype_Technical_Specification%20v1.0.docx)
4. [`docs/M0_ARCHITECTURE_DECISIONS_2026-08-29.md`](docs/M0_ARCHITECTURE_DECISIONS_2026-08-29.md)
5. `docs/Aqlio_MVP_Implementation_Specification_v2.0.doc` for broader future context only.

Detailed M0 documents control current scope and participant behavior. Prioritize conflicts by user safety/privacy, the M0 implementation package, UX/UI specification, technical specification, the approved architecture addendum, and then broader MVP context.

The original binary file previously named `AGENTS.md` is preserved at `docs/archive/AGENTS_original.docx`.

## Product principles and journey

Apply AI for Everyone, Simplicity by Design, Leverage the Best, Cost Optimization First, Progressive Complexity, and Invisible Infrastructure.

Primary journey: describe an idea; optionally evaluate; define the solution; build with the
first document template; test; improve safely; retest; run inside Aqlio; optionally publish.
My Projects must support independently saved/resumable projects and creating another project.
Selection automatically adds/prepares documents. Changed drafts need fresh testing; publication
snapshots remain immutable. Never claim durable persistence for in-memory smoke environments.

Use participant language such as Workspace, Project, Ask My Documents, Add Documents, Test, Deploy, My Assistant, and Portfolio. Never expose infrastructure/provider terminology in participant UI.

Participant **Deploy** means publishing an immutable approved assistant version inside Aqlio. It does not provision infrastructure.

## Architecture boundaries

Separate Streamlit UI, application services, domain models/rules, ports, adapters, infrastructure, and configuration. Keep business rules out of widgets. The domain must not depend on Streamlit, a provider, hosting vendor, or database.

Use provider-neutral AI and storage ports. Provider/model/credential selection remains server-controlled. Do not use Streamlit session state as authoritative persistence.

## M0 limits

Do not add participant-facing infrastructure integration, BYO keys, model selection, multiple templates, payments, marketplaces, multi-agent workflows, arbitrary tools, complex builders, public-by-default sharing, enterprise administration, native apps, or per-user infrastructure unless explicitly requested.

## Privacy, security, and errors

Documents and answers are private by default. Never commit secrets, uploads, user databases, generated indexes, private logs, or analytics exports. Never routinely log full document content, questions, prompts, or answers.

Validate file type/size server-side, generate safe storage names, scope storage/retrieval by workspace/project/version, and prevent horizontal access. Translate failures into plain-language explanations and recovery actions without stack traces, provider details, secrets, or internal identifiers.

## Engineering and verification

Prefer small typed modules and minimal dependencies. Tests must use deterministic fake providers by default; live calls are opt-in and never part of standard checks.

Required commands:

```bash
streamlit run streamlit_app.py
python -m pytest
python -m pytest tests/evals
ruff check .
ruff format --check .
mypy app
```

Test project creation, template selection, validation, isolation, lifecycle/readiness, publication eligibility and immutability, shared access/revocation, invalid configuration, provider failures, retries, and participant-language restrictions.

A change is done only when behavior works, relevant tests pass, language remains non-technical, recovery/privacy boundaries are handled, credentials/private data remain uncommitted, documentation is current, and the primary journey remains usable.

## Working approach

Before coding, inspect current code/tests and relevant authority, state material assumptions, implement the smallest complete change, run applicable checks, and report verification and limitations. Ordinary reversible decisions within the approved architecture do not require confirmation.
