# Aqlio M0 product and domain alignment — 2026-09-05

Requirements 1–69 in the owner's 2026-09-05 Aqlio M0 update are authoritative for the product
journey and controlled implementation sequence. They supersede the original document-only journey
where they conflict while retaining the approved layered architecture, isolation, grounding,
security, versioning, publication, sharing, allowance, and audit controls. Ask My Documents remains
the operational M0 product template. A bounded synthetic Eligibility & Recommendation Advisor is
the second architecture-test reference application; it is not a production admissions product or
arbitrary application-generation capability. Initial staging remains `AQLIO_AI_MODE=fake`.

## Participant flow

Idea → optional Evaluate → Define → Build → Test → Improve → Apply → Test Again → Run in Aqlio →
Approve → optional Publish in Aqlio → Get My Application Code.

This update implements and stops after Phase F. Railway readiness remains intentionally deferred.
Export packages are generated, structurally validated, and exercised in a clean independent runtime
using deterministic fake mode without Aqlio or paid-provider availability.

- My Projects lists independent projects by ID, including duplicate names. Continue Building
  resumes from persisted readiness; navigation state is not authoritative.
- Idea evaluation is qualitative decision support, not success prediction. Fake mode uses
  explicitly labeled deterministic guidance. The same generation port supports managed mode
  later, with authorization, allowance/rate checks, bounded output, and usage/failure records.
- Definition fields save on edit/blur. Continue first creates the idea; evaluation is optional.
- File selection automatically validates, adds, and prepares. Failed attempts remain visible
  with Try Again; ordinary reruns do not automatically retry failed work or duplicate versions.
- Test shows grounded answers/sources or abstention, then asks the participant whether the answer
  was correct. Generation alone never passes a test. Only “Yes, it worked” records current-version
  test success; “Needs Improvement” captures feedback and carries it into Improve. Run remains a
  peer action, not an extra publishing gate; all other readiness checks remain enforced.
- Improve accepts response guidance plus a Concise/Balanced/Detailed style. The participant reviews
  the proposed configuration change and explicitly applies it before retesting. Style guides
  presentation but never truncates information required by factual, complete-list, summary, or
  comparison questions. Better documents remain the other supported improvement. Unsupported
  requests are identified honestly and cannot be applied.
- Improve Look & Experience offers controlled title, user instructions, question-box placement,
  prose/list/table answer layout, compact/expanded citation presentation, and display-detail
  settings. A participant describes the goal, reviews the proposed structured change, explicitly
  applies it, sees it in the Working Version, and retests. Unsupported requests cannot be applied.
- Improvements create a new version and invalidate prior test/readiness/run evidence.
  Adding documents preserves the chosen response guidance/style and requires retesting.
- Publish Application combines internal readiness confirmation and immutable private publication.
  It is not commercial infrastructure deployment. Link sharing requires explicit consent.
- Publications remain discoverable after navigation/reconstruction, including legacy records;
  old links continue to use their original immutable configuration and content.

## Product and domain model

- **Application Specification** is the versioned, typed description of one Ask My Documents
  application: identity, behavior configuration, UI configuration, authorized document IDs, and
  approval state. It is the future common input to both Aqlio runtime behavior and export building.
- **Working Version** is the current mutable-by-replacement `ProjectVersion`. Applying a supported
  improvement creates a new version; it never mutates an earlier version in place.
- **Successful test confirmation** is a participant judgment attached to the exact current Working
  Version. Generating a non-abstaining answer creates only a pending assessment. “Yes, it worked”
  records success; “Needs Improvement” records feedback and does not count as success.
- **Applied Improvement** is a reviewed, supported configuration change persisted in a new Working
  Version. Unsupported requests remain proposals with an explanation and cannot be represented as
  applied changes.
- **Approved Version** is an immutable `ApprovedVersionSnapshot` of the exact tested Application
  Specification accepted by its owner. Approval is separately authorized, never mutates an earlier
  approval, and does not publish, export, or deploy anything.
- **Published Version** is the existing immutable Aqlio-hosted `Publication`. It is distinct from
  the Working Version and from commercial deployment. Later changes do not alter it.
- **Export Package** is an immutable, owner-scoped record linked to exactly one Approved Version and
  project/version identity. Its private ZIP contains the minimal standalone application runtime,
  approved structured configuration, manifest, setup/tests, and Railway guidance. It excludes
  source documents, secrets, other users, and Aqlio platform code.

The version relationship is:

`Project → Working Version → participant test confirmation → Approved Version Snapshot → Export Package`

`Publish in Aqlio` creates a separate immutable Published Version from an eligible Working Version.
`Run in Aqlio` uses the Working Version. `Export for Commercial Deployment` will produce code and
instructions from an Approved Version; it will not deploy that code or provision Railway.

## Controlled phase boundary

- **Phase A complete:** documentation and framework-neutral domain types represent Application
  Specification, Working, Approved and Published versions, improvements, and Export Package without
  implementing export.
- **Phase B complete:** test success requires participant confirmation; feedback flows into a
  review/apply/retest loop; irrelevant retrieval abstains; response completeness follows the task;
  and unsupported improvements are disclosed honestly.
- **Phase C complete:** supported UI/UX changes are reviewed, applied to a new Working Version,
  persisted in its Application Specification, rendered by Test/Run, and require fresh testing.
  Existing Published Versions retain their original configuration until explicitly republished.
- **Phase D complete:** a successfully tested current Working Version can be reviewed and explicitly
  approved as an immutable, authorized snapshot. Later improvements require fresh testing and a new
  approval. Run in Aqlio, Publish in Aqlio, and Get My Application Code are shown as distinct next
  choices without making approval itself publish, export, or deploy anything.
- **Phase E complete:** Get My Application Code builds only from the current immutable Approved
  Version, validates required files/version/manifest, scans for secrets and platform boundaries,
  stores a durable private Export Package record, and offers an authorized ZIP download. Private
  source documents are excluded by default.
- **Phase F complete:** the exported package creates a clean Python 3.12 environment, installs only
  declared dependencies, runs package-owned tests for TXT/PDF/DOCX extraction, grounded answers,
  complete lists, abstention, prompt-injection resistance and approved UI configuration, then starts
  Streamlit independently and passes its health check. `scripts/validate_export_runtime.py` makes
  this validation reproducible.
- **Deferred by design:** Phase G Railway readiness and any real-provider validation.

## Persistence and safety

Migration `20260830_0003` adds JSON journey metadata to projects and configuration to versions
and publications. Migration `20260905_0004` adds immutable Approved Version snapshots. Core
identity, tenancy, asset, usage, and lifecycle relations remain relational. Migration
`20260905_0005` adds immutable, owner-scoped Export Package records; ZIP bytes remain behind the
private storage port.
Migration `20260906_0007` adds participant-validation evidence to new Approved Version snapshots.
The nullable field keeps earlier immutable approvals readable without inventing historic evidence.
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
participant-confirmed test/run/publish gating, response configuration, immutable old publications,
retest on changes, relevance abstention, complete-list answers,
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
5. Mark an incorrect answer Needs Improvement, review/apply the carried feedback and response
   style, retest, confirm success, and Run Application with an answerable question.
6. Optionally publish privately, enable sharing explicitly, check a clean-session link, and revoke.
7. Improve the draft again; verify the previously shared publication remains unchanged.
8. Return to My Projects, start another idea, and resume both independently.

No Railway, object storage, OpenAI credentials, or Google OIDC is provisioned. No persistence or
GO pilot decision is claimed. Do not merge/overwrite main as part of this revision.

## Focused post-test clarification

The participant sees Working Version and Published Version. After each test answer, Aqlio asks
“Did your application answer this correctly?” Generation does not imply success. After participant
confirmation, Aqlio shows “Your application is working with this question”, followed by Test Again,
Improve, Run Application, and Publish Application. Document additions/refresh live under Improve.
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

## Generalized post-export behavior correction

Railway validation of immutable Export Package v6 exposed that deterministic retrieval passages
were being surfaced as answers. Future Working Versions and exports now use a separate
question-aware answer step: factual questions select only the responsive fact, completeness
requests select all supported matching items without surrounding text, summaries synthesize
relevant evidence, comparisons use structured relevant evidence, and unsupported questions
abstain. Citations are limited to evidence chunks used by the deterministic answer. Managed mode is
instructed to uphold the same semantic contract; participant display preferences remain
presentation guidance only.

TXT validation now rejects content that is clearly RTF despite a `.txt` extension and tells the
participant to save plain UTF-8 text. This prevents formatting control codes from entering future
answers. Immutable Export Package v6 is unchanged; only exports created later through the existing
Approved Version process inherit this correction.

The remaining gap toward testable, specification-driven application behavior and the recommended
next bounded phase are documented in `SPECIFICATION_DRIVEN_APPLICATION_GAP.md`.

## Specification driven Ask My Documents evaluation

Each Working Version now derives a typed Ask My Documents Behavioral Specification from the
participant's problem, intended users, outcome, supported template capabilities, input/output
contract, grounding/citation/abstention/completeness rules, approved UI choices, constraints, and
stable acceptance criteria. Requirement identifiers (`AMD-*`) trace to acceptance identifiers
(`AC-*`) and exact-version evaluation results.

The participant can see Pass, Fail, and Not Yet Tested states and run the evaluation again.
Confirming a successful question also runs the deterministic conformance suite; one successful
question alone no longer permits approval. Every required criterion must pass for the exact Working
Version, followed by explicit participant approval. Managed-provider semantic fidelity remains Not
Yet Tested in fake mode and is optional rather than falsely passed.

A failed result can be carried into Improve. Applying the improvement creates a new Working Version,
invalidates the old evaluation and participant test evidence, and requires the applicable acceptance
and regression checks again. New Approved Version snapshots and future export manifests include the
Behavioral Specification schema and evaluation provenance. Earlier Approved, Published, and Export
artifacts remain unchanged.
