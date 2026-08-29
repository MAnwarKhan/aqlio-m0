# M0 Evaluation Expectations

Deterministic evaluations are the primary CI gate and make no provider calls.

- Supported answer: contains a fact present in authorized retrieved evidence and at least one citation.
- Citation integrity: every citation chunk ID belongs to the exact retrieved context; fabricated IDs fail closed.
- Abstention: unsupported questions return the approved uncertainty message and no citation or provider call.
- Injection resistance: operational instructions in document text are excluded; they cannot change access, allowances, publication, or sharing.
- Isolation: retrieved chunks belong to the authorized project and current version only.
- Allowance: authorization, readiness, rate limit, and allowance checks complete before an adapter call.
- Provider failure: timeout retries stop at the configured bound and persist only a normalized category.
- Publication: shared queries use immutable publication chunks, not the mutable current project version.

The opt-in live suite uses the same trusted citation contract. It is a small staging smoke check, not the standard correctness gate. Enabling it without explicit credentials, call cap, and estimated-cost cap fails safely.
