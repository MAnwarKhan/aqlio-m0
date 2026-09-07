# Statistics answer regression (staging only)

Base: 2e70140. The exact uploaded seven-page PDF reproduced the Cedar-7 question echo
on page 7 and a Seabrook question fragment on page 1 in fake mode. PDF extraction and
page metadata were correct. Retrieval uses lexical matching (stored embeddings do not
rank these results). Citation-request wording raised the matching threshold and omitted
the page-2 calculation; fake generation selected isolated high-overlap question lines.

The fix removes trailing citation instructions from subject matching, orders bounded safe
neighbors by document position, rejoins wrapped prose, excludes question sentences, and
keeps up to two same-page passages for explanations. No study names, values or pages are
hard-coded in application code. Managed instructions prefer primary calculations and treat
explicitly missing information as a citable fact. Existing response parsing and UI rendering
already use generated answer text and validated citation metadata.

No new migration, dependency, schema, storage or UI change. Existing page-citation migration
0008 remains required only if the installation has not yet applied the earlier release.
No uploaded PDF or API credential is committed.

## Verification

Run in Python 3.12 with development and pilot dependencies installed:

```sh
AQLIO_STATISTICS_PDF=/absolute/path/introduction-to-statistics-aqlio-test-course-pack.pdf python -m pytest
python -m pytest tests/evals
ruff check .
ruff format --check .
mypy app
streamlit run streamlit_app.py --server.headless true
```

Original-PDF tests cover working and immutable published/shared answers for both questions.
They skip explicitly when the external PDF is absent; synthetic regressions always run.
Managed adapter tests verify request evidence, response parsing and trusted page mapping with
stubbed responses. They do not establish live model accuracy. Paid tests remain opt-in.

## Deployment and exact smoke test

1. Confirm Streamlit deployment repository is `MAnwarKhan/aqlio-m0`, branch `staging`,
   entry point `streamlit_app.py`. Deploy the tested staging commit; never merge into main.
2. In the app's private settings, verify these are top-level secrets, outside any TOML table:
   `AQLIO_AI_MODE = "managed"`, `OPENAI_API_KEY` (existing secret),
   `OPENAI_GENERATION_MODEL` and `OPENAI_EMBEDDING_MODEL` (your approved available models).
   Keep existing storage/authentication/budget settings. Do not paste secrets into chat or logs.
   A key alone leaves the application in fake mode. Explicit fake mode remains credential-free;
   incomplete managed configuration fails closed. No automatic paid-mode activation was added.
3. Save settings and reboot the app. In-memory workspaces reset on restart. Create a fresh
   private project named `Statistics grounding smoke test`, choose Ask My Documents if prompted,
   and upload `introduction-to-statistics-aqlio-test-course-pack.pdf`. Wait for preparation.
   For a durable existing project use Improve → Refresh PDF Documents if page metadata is old.
4. Submit exactly:
   `What is Cedar-7's sample variance, and why do we divide by 6? Please cite the page where you found the information.`
   Pass: 8 min², squared deviations 48, seven sample observations, n − 1 = 6,
   calculation 48 / 6 = 8; primary source page 2 (page 7 may also be cited if used).
   Fail: question echo, missing calculation, only page 7, or fabricated page.
5. Submit exactly: `What is Seabrook's exact correlation coefficient?`
   Pass: explicitly says it is not provided/reported, invents no coefficient, cites page 7.
6. Ask: `Does the Seabrook study prove that library attendance causes higher quiz scores?`
   Pass: no; observational association does not establish causation, with page 7 evidence.
7. Confirm successful tests through the existing readiness flow, publish a new version,
   and repeat steps 4–5 in Run Application and its private shared link if sharing is enabled.
   Existing published snapshots remain unchanged; do not expect an old snapshot's evidence to refresh.
8. For managed mode, inspect the existing administrator usage view for successful OpenAI
   generation events. Never display environment variables or the secret value. Verify a normal
   answer and source render without a traceback. If a provider call fails, expect the existing
   plain-language recovery message, not a fake answer.

Actual cloud secret values and live model behavior must be verified in this smoke test;
local tests cannot certify the deployed configuration. OpenAI response-format reference:
https://developers.openai.com/api/docs/guides/structured-outputs
