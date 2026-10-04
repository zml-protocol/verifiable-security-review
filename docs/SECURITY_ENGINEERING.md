# Security Engineering Notes

This project is security engineering first: establish the vulnerable behavior, define what must be
true for the claim, verify concrete evidence, and refuse to overstate unsupported conclusions. The
LLM is one investigative component inside that workflow.

## Vulnerability validation workflow

Real-fix candidates use a fixed escalation order:

### TEST — use the fix's regression test

Apply a regression test from the fix commit to both revisions. It qualifies only when it exercises
the claimed security behavior, fails on the parent, and passes on the fix. A parent compile failure
alone is not a vulnerability reproduction.

### POC — use an advisory-linked proof of concept

If there is no qualifying regression test, use a PoC explicitly linked from the advisory's
references and run it against both revisions under the same assumptions.

### PROBE — build a minimal local differential probe

If neither route exists, construct a small probe from the advisory and fix diff within a 60-minute
review boundary. Its job is only to demonstrate the claimed parent/fix effect—not to become a broad
exploit framework.

Across all three routes:

- Use the same triggering input and environment assumptions on both revisions.
- Record benign controls when they distinguish the vulnerability from normal behavior.
- Keep the reproduction local and scoped to the claim.
- Stop at the frozen review boundary instead of reading arbitrary surrounding code until the story
  becomes convincing.
- Treat executable behavior as one layer; author exact code requirements separately.

The SiYuan fixture is a representative example: one HTTP request caused the parent revision to
copy a local file into web-accessible assets, while the fixed revision produced no asset. That
behavioral flip was then separated from the exact entry and guard statements used for scoring.

## False-positive controls

### Negative claims

Early fixtures included nearby but false hypotheses. RD later used mechanically substituted CWE
claims and required author plus two independent judges to agree that both revisions were
`NOT_SUPPORTED`. In RD v2, the single qualified negative task produced 0/2 false-supported
revision conclusions. The denominator is intentionally reported because one control does not prove
a general false-positive rate.

### Independent adjudication

Requirement truth was authored before judges saw it. Two fresh, isolated judge sessions labelled
the same evidence bundle. A fixture was admissible only when the three labels agreed; ambiguity,
missing requirements, or unexpressible anchors remained visible and could reduce N after reserves
were exhausted.

### Provider conformance

Provider queries were challenged with true and near-miss false edges before real measurement. The
RD conformance gate admitted nine relation groups and observed 0 false-to-`VERIFIED` outcomes across
22 false synthetic cases. `PARTIAL` providers retained named blind spots rather than being promoted
to full support.

### Unsupported is not contradicted

These states are intentionally separate:

- **Unsupported:** the current evidence vocabulary/provider cannot express or verify the link.
- **Unverified:** the provider did not prove the proposed link.
- **Contradicted:** a conservative check established that the proposed shape/direction is wrong.

Collapsing them would turn tool limitations into false security conclusions.

## Fail-closed design: incidents that became controls

### Invalid regex was a harness issue

In 1B stage 2, one agent supplied a malformed `git grep -E` pattern. The harness initially called it
a repository `git_error`. The frozen experiment stayed failed; the tool was corrected in the next
version to return the caller-visible `bad_pattern` input error. A tool bug was not charged to model
reasoning or erased from the report.

### Context leakage forced a stage rerun

The first stage-1 harness ran agents inside paths containing case and condition names, and Claude
Code could include working-directory/repository context in its system prompt. Even though visible
outputs did not quote those strings, all 80 runs violated the later isolation invariant. They were
retained only as sensitivity evidence; stage 1 was rerun under v1.1 from external empty temporary
directories with empty memory.

### Truth ambiguity was not rescored

P-Hybrid-2 unit R016 exposed two defensible readings of a one-step Go object-composition relation.
Independent adjudication marked the hop false while the author/provider interpretation accepted it.
The primary label stayed frozen, the 13 affected verified occurrences were reported, and later
reports disclosed that one P-extension chain depended on the disputed interpretation. No golden
label was rewritten to improve results.

### RD v3 stopped before model calls

An independent held-out curator used a complete Go send statement, while the frozen validator
accepted only a narrower unpublished node whitelist. The public contract and executable acceptance
language disagreed. The one-shot gate returned `CALIBRATION_INVALID`: no case repair, no replacement
batch, no Claude sessions, no spend, and no formal tranche.

## Engineering lessons

1. **Make acceptance languages executable and public.** Natural-language contracts are not enough
   when AST granularity determines validity.
2. **Separate verdict, evidence, and tool coverage.** A correct attribution can coexist with a wrong
   requirement or an incomplete provider path.
3. **Treat provenance as a security control.** Hashes, sealed artifacts, revision-scoped anchors,
   and score-before-review rules reduce opportunities for accidental adaptation.
4. **Prefer explicit blind spots to optimistic inference.** A human reviewer can evaluate an
   unsupported link; a falsely verified edge contaminates the whole chain.
5. **Preserve negative results.** The v2 0/5 chain result and the v3 premeasurement stop are useful
   because they identify exactly where trust should end.
