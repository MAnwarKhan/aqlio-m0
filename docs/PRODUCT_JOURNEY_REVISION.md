# Product journey revision — 2026-08-30

Implements the owner's Product Direction Clarification & UX Revision (received text ends
mid-section 45). This supersedes the original document-only product framing, while retaining
the approved layered architecture and security controls. No additional template or external
service is introduced. Initial staging remains `AQLIO_AI_MODE=fake`.

## Participant flow

Idea → optional Evaluate → Define → Build → Test → Improve → Test Again → Run → optional Publish.

- My Projects lists independent projects by ID, including duplicate names. Continue Building
  resumes from persisted readiness; navigation state is not authoritative.
- Idea evaluation is qualitative decision support, not success prediction. Fake mode uses
  explicitly labeled deterministic guidance. The same generation port supports managed mode
  later, with authorization, allowance/rate checks, bounded output, and usage/failure records.
- Definition fields save on edit/blur. Continue first creates the idea; evaluation is optional.
- File selection automatically validates, adds, and prepares. Failed attempts remain visible
  with Try Again; ordinary reruns do not automatically retry failed work or duplicate versions.
- Test shows grounded answers/sources or abstention. Publishing is offered after a successful current-version test. Run is a peer action,
  not an extra publishing gate; all other readiness checks remain enforced.
- Improve accepts a description plus an explicit short/standard answer-length choice.
  **Only that choice changes behavior.** It is not a natural-language autonomous builder;
  summaries, cross-document comparisons, and new engines are not implemented. Better documents
  are the other supported improvement. Grounding/citations remain mandatory.
- Improvements create a new version and invalidate prior test/readiness/run evidence.
  Adding documents preserves the chosen answer length and requires retesting the new version.
- Publish Application combines internal readiness confirmation and immutable private publication.
  It is not commercial infrastructure deployment. Link sharing requires explicit consent.
- Publications remain discoverable after navigation/reconstruction, including legacy records;
  old links continue to use their original immutable configuration and content.

## Persistence and safety

Migration `20260830_0003` adds JSON journey metadata to projects and configuration to versions
and publications. Core identity, tenancy, asset, usage, and lifecycle relations remain relational.
Existing template/policy columns are retained with fallback for old records. Apply
`alembic upgrade head` before running this code against an existing SQL database; back up first.
No live migration is performed by this revision. Downgrading drops the new journey/configuration
fields and must not be used as a production rollback without backup/recovery planning.

Definition and improvement descriptions are private project data, not audit metadata or prompts
for document answering. Draft chunk replacement is atomic after all preparation calls succeed;
failure usage remains recorded. No raw document/idea/question content is added to routine logs.

The default development identity is shared. In-memory state can disappear on process restart;
UI warnings require sample data only. SQLAlchemy/local-storage restart tests demonstrate adapter
behavior, **not live Railway/S3/OIDC durability or pilot readiness**.

## Credential-free verification

Automated coverage includes optional evaluation, allowance/failure/isolation gates, duplicate-name
projects, definition autosave/navigation, DOCX auto-preparation, repeat reruns, visible failures,
test/run/deploy gating, short-answer configuration, immutable old publications, retest on changes,
atomic failed rebuilds, legacy publication discovery, SQL reconstruction, and additive migration.
Streamlit AppTest substitutes only the file-uploader boundary (it lacks file-selection support).
Managed-adapter tests use a stub client, never paid API calls.

The managed adapter retains the existing Responses interface and structured output, with
bounded output and storage disabled, checked against the
[official Responses API reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).

Local browser checks cover idea creation, definition, build navigation, temporary-mode messaging,
and visual layout. The deployed Streamlit URL has not been verified for this revision.
Restart the Streamlit process after code deployment: a cached service instance from an older
code version is not a valid hot-reload verification environment. Restarting the temporary demo
discards its in-memory projects, as the participant warning explains.

## Staging smoke acceptance after approved deployment

1. Confirm fake AI, development identity, temporary-state warning, and sample data only.
2. Enter an idea, skip or run evaluation, fill the short definition, and start building.
3. Select a supported DOCX. Without a second Add action, see Ready and Test My Application.
4. Ask an answerable question and inspect its source; ask an unsupported question and see abstention.
5. Choose shorter answers in Improve, retest, and Run My Application with an answerable question.
6. Optionally publish privately, enable sharing explicitly, check a clean-session link, and revoke.
7. Improve the draft again; verify the previously shared publication remains unchanged.
8. Return to My Projects, start another idea, and resume both independently.

No Railway, object storage, OpenAI credentials, or Google OIDC is provisioned. No persistence or
GO pilot decision is claimed. Do not merge/overwrite main as part of this revision.

## Focused post-test clarification

The participant sees Working Version and Published Version. After a successful question:
“Your application is working with this question”, followed by Test Again, Improve,
Run Application, and Publish Application. Document additions/refresh live under Improve.
Internal deployment identifiers/states remain unchanged for compatibility; participant wording
uses Publish. Improvements require retesting and do not mutate existing publication snapshots.
Publishing an updated snapshot leaves prior links pinned to their original version.

Sharing shows Open Shared Application, Copy Link, and Stop Sharing instead of raw token text.
Only token hashes are persisted. If the owner loses the transient original link, they must
stop sharing and create a replacement; the system cannot recover a token from its hash.
Clipboard denial produces an honest recovery message, not a false success.

PDF extraction now expands typographic ligatures and applies whole-word corrections for the
reported documentaFon/invenFons/informaFon/Plalorm artifacts. This is deliberately PDF-only
and not a global F/l substitution or general spellchecker. The original affected PDF was not
provided: font-map corruption is plausible but unconfirmed. Regression tests stub extracted
PDF text, then verify normalized retrieval/answers and immutable publications. Refresh PDF
Documents under Improve reparses stored PDFs into a new Working Version; old Published
Versions deliberately retain their original text. No live files are rewritten automatically.
