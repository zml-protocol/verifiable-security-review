# RD v3 protocol-delta final review

Status: **APPROVE DESIGN FOR CONSTRUCTION-SPEC FREEZE**

Reviewed baseline: `c8cdafa` (`V3-PROTOCOL-DELTA.md`). This review authorizes only the next
non-model step: construction and freeze of the synthetic development/held-out specifications. It
does not authorize paid development calls, held-out unsealing, fixture selection, or formal runs.

## Decision audit

| Decision | Review result |
|---|---|
| v2 remains immutable; v3 does not rescue or rescore it | PASS |
| exactly four interventions; no new qualifier, matcher, relation, or chain semantics | PASS |
| terminal rule: failed gate closes; passed gate permits one fresh tranche; no v4 | PASS |
| A held-out N=20, gate 16/20 plus all cell/structural guards | PASS |
| provider false→VERIFIED is unsafe; PARTIAL/UNSUPPORTED are valid outcomes | PASS |
| fresh real target 3 Go + 3 Python, three reserves/language, reduce-N/no backfill | PASS |
| provider freezes before fresh selection; disposition never replaces a fixture | PASS |
| conditional and full-sample B views are both mandatory | PASS |
| conditional B n=0 / 1–2 / ≥3 interpretation is frozen | PASS |
| checkpoint is append-only and never promoted to final submission | PASS |
| C1 precedes C2; target CWE remains hidden; no-confident output is allowed | PASS |
| exact v2 model/CLI, no fallback, A/B/C cumulative budget remains $3→$6→$7 | PASS |
| held-out ceiling $60; formal ceiling $7 × frozen formal task count, max $84 | PASS |
| user authorization is staged; insufficient formal authorization starts no task | PASS |
| score-before-transcript inspection and fail-closed provenance remain | PASS |

## Clarifications made during final review

Three inherited semantics were made explicit without opening a new intervention:

1. B continues to report both agent-graph `FULL_CHAIN` and v2's stricter correct verified
   implementation. A chain under a truth-mismatching A specification is not verified reasoning.
2. C1/C2 non-submission is valid model behavior, not automatically a harness failure. C1 absence,
   C2 not reached, and C2 missing after C1 lock are distinct; missing C2 is not
   `NO_CONFIDENT_CWE`.
3. C2 compares against a hidden frozen **claim** label: the real task's selected CWE or the negative
   control's substituted CWE. It does not compare a control against the original advisory CWE.

These corrections preserve PREREGISTRATION.md §15.5–§15.8 and prevent accidental metric or control
drift.

## No open methodological parameter

The design now has no open model, sample-size, threshold, relation, denominator, C construct, or
measurement-budget choice. Construction specifications must instantiate this design without adding
one. Any requested change to these decisions requires stopping before held-out construction and a
new explicit review; it may not be introduced as an implementation detail.

The next allowed sequence is:

1. write and freeze synthetic construction specifications, development cases, hidden-challenge
   commitment procedures, and selection-seed procedure;
2. request a separate development/pilot spending authorization before any paid model call;
3. only then implement and calibrate against development data.
