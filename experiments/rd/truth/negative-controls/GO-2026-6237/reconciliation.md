# GO-2026-6237 negative-control reconciliation

The author labels were committed at `008f95d` before either judge received the byte-identical prompt
(SHA-256 `fcc2bbe5c7cfea26327b037b2591fc76c34537766f07e901ec0a56819782d17a`). Judge A was a fresh
isolated `gpt-6.1-sol` session; Judge B was a fresh isolated `deepseek/deepseek-flash` session. Raw
transcripts are retained.

| candidate | author (vuln/fixed) | Judge A (vuln/fixed) | Judge B (vuln/fixed) | qualifies |
|---|---|---|---|---|
| 01 — CWE-352 CSRF | NOT_SUPPORTED / NOT_SUPPORTED | NOT_SUPPORTED / NOT_SUPPORTED | NOT_SUPPORTED / NOT_SUPPORTED | yes |
| 02 — CWE-22 Path Traversal | NOT_SUPPORTED / NOT_SUPPORTED | INDETERMINATE / INDETERMINATE | NOT_SUPPORTED / NOT_SUPPORTED | no |
| 03 — CWE-79 XSS | NOT_SUPPORTED / NOT_SUPPORTED | NOT_SUPPORTED / NOT_SUPPORTED | NOT_SUPPORTED / NOT_SUPPORTED | yes |

The frozen rule selects the first qualifying candidate, so this fixture's negative control is
**candidate-01: CWE-352 Cross-Site Request Forgery**. Candidate 02 cannot qualify because Judge A did
not find the supplied evidence dispositive. Candidate 03 also qualifies but is not selected because
it follows candidate 01. No label was rerun or rewritten.

Mechanical schema validation accepted all three label files and recomputed the qualifying set as
`[candidate-01, candidate-03]`, with `candidate-01` selected.

