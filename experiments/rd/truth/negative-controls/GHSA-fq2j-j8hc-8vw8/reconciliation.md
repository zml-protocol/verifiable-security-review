# GHSA-fq2j-j8hc-8vw8 negative-control reconciliation

The author labels were committed at `7ed8539` before either judge received the byte-identical prompt
(SHA-256 `68fbe379f976f5bac93ae4c4d228f2fa0a0a0360bf6691cf67ce55c82343fa12`). Judge A was a fresh
isolated `gpt-6.1-sol` session; Judge B was a fresh isolated `deepseek/deepseek-flash` session. Raw
transcripts are retained.

| candidate | author (vuln/fixed) | Judge A (vuln/fixed) | Judge B (vuln/fixed) | qualifies |
|---|---|---|---|---|
| 01 — CWE-22 Path Traversal | SUPPORTED / INDETERMINATE | SUPPORTED / INDETERMINATE | SUPPORTED / INDETERMINATE | no |
| 02 — CWE-79 XSS | INDETERMINATE / INDETERMINATE | INDETERMINATE / INDETERMINATE | INDETERMINATE / INDETERMINATE | no |
| 03 — CWE-89 SQL Injection | INDETERMINATE / INDETERMINATE | INDETERMINATE / INDETERMINATE | INDETERMINATE / INDETERMINATE | no |

No candidate has all six author/Judge A/Judge B revision cells labelled `NOT_SUPPORTED`, so this
fixture has **no negative control**. The three parties agree on every cell. No label was rerun or
rewritten.

Mechanical schema validation accepted all three label files and recomputed an empty qualifying set
with `selected: null`.

