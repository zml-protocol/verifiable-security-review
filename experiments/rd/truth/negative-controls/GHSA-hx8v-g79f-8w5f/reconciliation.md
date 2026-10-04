# GHSA-hx8v-g79f-8w5f negative-control reconciliation

The author labels were committed at `943b14e` before either judge received the byte-identical prompt
(SHA-256 `96ddd910b12de2b92c0a7e5302fd78335da5427369382c5a8ec3c2d7420874a9`). Judge A was a fresh
isolated `gpt-6.1-sol` session; Judge B was a fresh isolated `deepseek/deepseek-flash` session.
Raw transcripts are retained.

| candidate | author (vuln/fixed) | Judge A (vuln/fixed) | Judge B (vuln/fixed) | qualifies |
|---|---|---|---|---|
| 01 — CWE-502 Deserialization | NOT_SUPPORTED / NOT_SUPPORTED | INDETERMINATE / INDETERMINATE | NOT_SUPPORTED / NOT_SUPPORTED | no |
| 02 — CWE-601 Open Redirect | SUPPORTED / SUPPORTED | SUPPORTED / SUPPORTED | SUPPORTED / SUPPORTED | no |
| 03 — CWE-611 XXE | NOT_SUPPORTED / NOT_SUPPORTED | INDETERMINATE / INDETERMINATE | NOT_SUPPORTED / NOT_SUPPORTED | no |

No candidate has all six author/Judge A/Judge B revision cells labelled `NOT_SUPPORTED`, so this
fixture has **no negative control**. Candidate 02 is positively supported in both revisions by all
three assessors. For candidates 01 and 03, Judge A did not find absence across the 194k-line package
surface dispositive, while the author and Judge B did. The frozen procedure provides no evidence
amendment, relabel, or rerun after judge output. No label was rewritten.

Mechanical schema validation accepted all three label files and recomputed an empty qualifying set
with `selected: null`.

