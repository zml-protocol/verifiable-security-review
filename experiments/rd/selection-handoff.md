# RD fixture selection — handoff for the manual admissibility checks

This hands off the one part of RD fixture selection that reads vulnerability detail and establishes
executable truth (which, on the POC/PROBE route, means building a working exploit for a real CVE).
Everything mechanical — the frozen script, the candidate pool, the hash-chained log, scoring,
reporting — stays with the main session. The manual checks are to be run by a separate agent/session
in an authorized security-research context.

Do not reproduce exploit mechanics in chat; record them only in the decision artifacts described
below.

## Where things stand

- Protocol: `PREREGISTRATION.md` §15 (frozen). Selection rules: §15.2.
- Selection script **frozen**: `experiments/rd/selection.py` (commit `3680e08`). Do **not** edit it.
  Every command after `pool` recomputes its sha256 and the pool sha256 and the log hash-chain, and
  aborts with `SELECTION_PROTOCOL_CHANGED` if any differ. A new rule needs a new protocol version
  reviewed by Codex, never an edit mid-selection.
- Candidate pool **written and committed** (`6285124`): `results/rd-candidate-pool.json`
  (871 Go, 1647 Python candidates, each in its frozen seeded order).
- Append-only, hash-chained log: `results/rd-selection-log.jsonl`.
- Two position-1 candidates have **passed the mechanical diff screen** and await a manual verdict:
  - Go #1 `GHSA-fq2j-j8hc-8vw8` (siyuan-note/siyuan): 3 source files, 8 non-test lines, no test in
    the fix commit → route POC, then PROBE.
  - Python #1 `GHSA-hx8v-g79f-8w5f` (berriai/litellm): 5 source files, 179 non-test lines, one test
    file in the fix commit (`tests/test_litellm/llms/test_file_search_responses.py`). Mechanical
    note already established: that test file does **not** reference the advisory's guard function or
    the smuggled parameter, so the TEST route likely does not cover the claimed behavior; expect to
    fall through to POC, then PROBE.
- Codex asked for a checkpoint: **do only these two position-1 checks, then stop** and show the
  decision log, so the first real use of each route (TEST, and POC→PROBE) can be confirmed before
  the queues are run down.

## The target of an executable-truth check (only this, nothing more)

Confirm the base/head behaviour flip: with one triggering input, the claimed effect occurs at the
**parent** commit and does **not** occur at the **fix** commit. That is all selection needs. Do not
explain the vulnerability mechanism, do not identify entry/behaviour/qualifier anchors, do not write
anything that belongs in the fixture's truth — that is a later, separate phase and must not be
learned now.

## Review boundary (hard limit)

While deciding admissibility you may read only: the advisory, the fix diff, the test files the fix
touches, and the build files. If deciding any criterion would require reading product source beyond
that, stop immediately and record `REVIEW_BOUNDARY_REACHED` (a rejection). Do not read "just one
more function".

## Routes to establish executable truth, in this fixed order

1. **TEST** — a regression test contained in the fix commit. Apply it to the parent: it must fail at
   the parent and pass at the fix. Only use this route if such a test actually exercises the claimed
   behaviour.
2. **POC** — a proof of concept linked from the advisory's own references. Run it against both
   revisions.
3. **PROBE** — if neither of the above exists, build a minimal probe from the advisory and the fix
   diff alone, within a **60-minute** time box, whose only job is to show the base/head flip.

## Per-candidate procedure

For the next candidate of a language (strictly in pool order), the main session has already run:

    uv run python experiments/rd/selection.py screen --language go      # or: --language python

which logged a `screen` outcome of `PASS` (or a mechanical rejection). For a `PASS` candidate, do
the manual check, then record the verdict with:

    uv run python experiments/rd/selection.py decide --id <ID> --verdict <VERDICT> \
        [--route TEST|POC|PROBE] --evidence "<one line: commands + base/fix result>"

`--route` is required only for `ACCEPTED`. `--evidence` is required for every verdict.

### Verdicts (frozen enumeration — do not invent new ones)

- `ACCEPTED` — every criterion holds; executable truth established via one route.
- `EXEC_TRUTH_UNAVAILABLE` — no test, PoC or probe within the boundary and the 60-minute box.
- `EXEC_TRUTH_NOT_CONFIRMED` — a test/PoC/probe ran, but the parent did not show the effect or the
  fix still did.
- `BUILD_UNAVAILABLE` — does not build/run locally, or needs an external commercial service or
  special hardware.
- `VENDORED_CODE` — the vulnerable code is in a vendored dependency, not the repository's own code.
- `REVIEW_BOUNDARY_REACHED` — a criterion could not be decided within the review boundary.

If you hit a situation none of these covers, **stop and report** — do not extend the enumeration.

### Decision artifact (per candidate)

Write `runs/rd/selection/<ID>/decision.md` recording **only**:

- route (`TEST` / `POC` / `PROBE`);
- the exact set of files read (must be within the review boundary);
- the exact commands run;
- the parent result and the fix result (pass/fail, or effect occurred / did not);
- elapsed probe time, if PROBE;
- the verdict and its frozen reason;
- whether the review boundary was reached.

Do **not** record how the vulnerability works, or any entry/behaviour/qualifier reasoning.

The `screen` step already fetched each candidate's fix commit and parent (no checkout) under
`.cache/rd/candidates/<ID>/`. The Python #1 advisory JSON is at
`runs/rd/selection/GHSA-hx8v-g79f-8w5f/advisory.json`.

## Infrastructure rules (do not work around)

- A fetch the server answers with "does not exist" (one of four frozen patterns) is a candidate
  property → `COMMIT_UNAVAILABLE`, a mechanical rejection, handled by `screen`.
- Any other fetch failure is infrastructure: the candidate stays pending and `screen` retries it,
  up to 3 times, then the whole selection halts with `INCONCLUSIVE_INFRA`. Accept that outcome; do
  not change the fetch method or skip a candidate. (Known risk: tensorflow/tensorflow appears at
  Python positions 3 and 8 and is large; a fetch timeout there is treated as infrastructure.)

## Do not

- Edit `selection.py`, the pool, or the log; the protocol is frozen.
- Read the provider-support tables (`results/rd-vocabulary.json`) during selection, or reject/accept
  by what a verifier can express.
- Reject or accept because an advisory looks easy or hard.
- Write any fixture-specific truth before the queue is frozen.
- Narrate exploit mechanics anywhere except the decision artifact's command/result lines.

## After the two checks

Stop. Report the two `decide` log entries and the two decision artifacts so the first use of each
route can be confirmed before the queues are run down to 4 primary + 2 reserve per language.
