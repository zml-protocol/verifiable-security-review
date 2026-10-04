# GHSA-mr3j-p26x-72x4 negative-control reconciliation

The author labels were committed at `8631754` before either judge received the byte-identical prompt
(SHA-256 `bbc6c319ca3a874535c8f84247d36a1dd8dd96005cdba24d96211801b5090923`). Judge A was a fresh
isolated `gpt-6.1-sol` session; Judge B was a fresh isolated `deepseek/deepseek-flash` session. Raw
transcripts are retained.

| candidate | author (vuln/fixed) | Judge A (vuln/fixed) | Judge B (vuln/fixed) | qualifies |
|---|---|---|---|---|
| 01 — CWE-918 SSRF | INDETERMINATE / INDETERMINATE | INDETERMINATE / INDETERMINATE | INDETERMINATE / INDETERMINATE | no |
| 02 — CWE-502 Deserialization | NOT_SUPPORTED / NOT_SUPPORTED | INDETERMINATE / INDETERMINATE | NOT_SUPPORTED / NOT_SUPPORTED | no |
| 03 — CWE-601 Open Redirect | NOT_SUPPORTED / NOT_SUPPORTED | INDETERMINATE / INDETERMINATE | NOT_SUPPORTED / NOT_SUPPORTED | no |

No candidate has all six author/Judge A/Judge B revision cells labelled `NOT_SUPPORTED`, so this
fixture has **no negative control**. Judge A did not find the package-wide absence evidence
dispositive for candidates 02 and 03; the frozen procedure provides no evidence amendment, relabel,
or rerun after judge output. No label was rewritten.

Mechanical schema validation accepted all three label files and recomputed an empty qualifying set
with `selected: null`.

