# Document answering and PDF page citations

This fix targets the deployed `staging` branch, starting at `62d85d4`. It preserves staging's
specification-driven application lifecycle, participant confirmation, approval/export controls,
advisor application, response styles, and existing feedback pipeline. The earlier standalone
package was based on `main`; do not apply that older package on top of this staging change.

## Behavior

PDF extraction retains physical page positions, including blanks. Page-aware chunks, persistent
assets, draft chunks, and immutable published chunks carry trustworthy page metadata. Compact
and expanded source displays both include the page; older records and non-PDF documents show
an unnumbered source passage rather than inventing a page. Existing PDFs require Refresh PDF
Documents (or a new upload after a temporary-workspace restart).

The three ranked retrieval matches now include safe neighbors on the same page, at most nine
passages. Existing staging scoring thresholds and complete-list retrieval are preserved. This
makes the mean following Cedar-7's introductory passage available to live generation.

Saved response guidance already reached generation in staging. This revision keeps that behavior
and moves the guidance from high-priority policy instructions into lower-priority request input.
Instructions require every requested part, supported calculations, units, honest identification
of missing information, and trusted page citations. Preferences cannot supply factual evidence
or override grounding. Published versions continue to retain their own immutable preferences.

Fake mode remains a deterministic source-selection demo. The Improve screen now explains that
arbitrary saved preferences require live AI to affect answers. No example answers are hard-coded.
This change alone does not turn on a live model or make the temporary shared workspace durable.

## Release

- Streamlit's observed deployment points to `staging/streamlit_app.py`. Merging this fix into
  staging allows the existing source integration to update the app.
- For SQLAlchemy installations, back up the database and run `alembic upgrade head` before
  starting the updated application. Migration `20260906_0008` follows staging's `0007`, adding
  nullable page fields. Legacy publications remain unchanged and have unknown page locators.
  The observed in-memory demo needs no SQL migration.
- A Streamlit process restart clears in-memory projects/files. Re-upload the sample PDF if
  necessary. Existing durable PDFs can be refreshed through Improve; publish a new version
  after testing to update shared citations. Old snapshots are not rewritten.
- Live AI still requires private server configuration: `AQLIO_AI_MODE=managed`, `OPENAI_API_KEY`,
  `OPENAI_GENERATION_MODEL`, and `OPENAI_EMBEDDING_MODEL`. Follow `DEPLOYMENT.md` for controlled
  activation and budgets. This source change does not provision keys or incur paid test calls.

## Verification

Credential-free regression tests cover page numbering across blank pages, bounded filtered
neighbors, non-PDF locators, persistence and migration from older schemas, immutable publication
locators, and saved guidance in working/shared requests. The actual seven-page course pack is
checked locally for page-2 mean evidence. The existing lifecycle/approval/advisor tests remain
part of the full suite. Standard tests do not establish real-model accuracy or preference
adherence; the live-provider test remains opt-in.

After enabling live AI, ask the single-part and multipart Cedar-7 questions. Expect mean 5,
median 4, mode 4, and the seven values 2, 4, 4, 4, 5, 5, 11 minutes, with page 2. Also test an
unsupported Seabrook correlation coefficient question; the document does not provide it.
