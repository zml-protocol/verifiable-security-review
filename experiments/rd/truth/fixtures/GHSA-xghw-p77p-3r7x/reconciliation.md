# fabric-ca (GHSA-xghw-p77p-3r7x) — adjudication: INADMISSIBLE (behavior INDETERMINATE); Go reserves exhausted

Three-way adjudication (§15.1). Judge A = gpt-6.1-sol (Codex CLI); Judge B = deepseek/deepseek-flash
(OpenCode); each fresh/isolated, one run, verbatim bundle. Mechanical reconciliation
(`agreement.check`; opaque→real via sheet-key).

## Result (not three-way unanimous)

| real item | kind | author | Judge A | Judge B | outcome |
|---|---|---|---|---|---|
| `entry-getuser-username` (item-08) | entry | REQUIRED | REQUIRED | REQUIRED | admissible |
| `behavior-escape-filter` (item-03) | behavior | REQUIRED | **NOT_REQUIRED** | REQUIRED | **INDETERMINATE** |

6 distractors all NOT_REQUIRED. Judge A additionally proposed a one-sided missing item: the SAME
behavior (fixed anchor = the `EscapeFilter` transform) but with the vuln context anchored at the
statement `sreq := ldap.NewSearchRequest(` rather than the author's sub-expression line
`fmt.Sprintf(lc.UserFilter, username),`.

## Root cause — author anchor-granularity error (not a fixture or verifier failure)

The behavior's fixed anchor (the `EscapeFilter` transform) was agreed by both judges. The
disagreement was purely the **absent-context anchor**: AC-2 requires "the first *statement* that
reads the transformed value", which is the `sreq := ldap.NewSearchRequest(...)` assignment; the
author anchored a sub-expression (`fmt.Sprintf(...)`) inside it. Judge A correctly rejected the
author's item and supplied the statement-level anchor.

Per the frozen rule, author truth is not edited after any judge has seen it (no "judge reveals the
right anchor → author fixes → resubmit" path), so the item stands INDETERMINATE and the fixture is
inadmissible — even though the behavior's substance was effectively agreed.

## Disposition

- Behavior INDETERMINATE → fixture inadmissible (§15.1).
- §15.2: the Go reserve queue is **exhausted** (oh-my-posh and fabric-ca were the two reserves; both
  inadmissible). No backfill: no re-screening, no quota-skipped promotion, no third reserve, no
  rescue of oh-my-posh/fabric-ca. **Go tranche is reduced to N=3** (SiYuan, Vikunja, DHCP).
- The two reserve failures (oh-my-posh: entry anchor on a coarse internal FuncDecl; fabric-ca:
  context anchored at a sub-expression) are **author anchor-selection errors**, recorded as such.
  Judge outputs retained permanently. Operator-approved; Codex selected (a) (no charter change).

Note: judge models for the fixture tranche are gpt-6.1-sol (A) and deepseek-flash (B); earlier
reconciliation files said "gpt-6-astra" (from the boundary-round config) — corrected here. The
adjudication content is unaffected.
