# RD fixture-selection — checkpoint change-log (tracked, durable)

Durable, committed record of the manual selection checkpoints. The fuller operator artifacts live
under `runs/rd/` (gitignored); this file is the tracked source of the durable facts so the
append-only selection state has a Git checkpoint before later positions build on it. The protocol
source of truth remains the frozen preregistration (§15), the committed `selection.py`/pool, and the
append-only `results/rd-selection-log.jsonl` — not this summary and not any memory note.

## Checkpoint #1 — 2026-10-02 (position-1, both languages)

First real use of the frozen selection protocol on fresh candidates. Reviewed by Codex; approved.

Verdicts (append-only log, last hash `65acaf03…`):

| candidate | repo | language | route (as logged) | verdict |
|---|---|---|---|---|
| `GHSA-hx8v-g79f-8w5f` | berriai/litellm | python | `PROBE` | `ACCEPTED` |
| `GHSA-fq2j-j8hc-8vw8` | siyuan-note/siyuan | go | `POC` | `ACCEPTED` |

Confirmed at this checkpoint:
- Both `ACCEPTED` verdicts valid; LiteLLM `PROBE` valid; SiYuan execution + verdict valid.
- Hash chain intact; `selection.py status` passes its own `checked()` gate (script sha256
  `1837f907…` equals the pool's recorded sha256; pool sha256 matches).
- The two `precheck/<ID>/decision.md` and the historical `selection/<ID>/decision.md` duplicates are
  byte-identical (LiteLLM `ed6f7194…`, SiYuan `d1a03d78…`).

Route-labeling clarification (applies to position 2+; does **not** rewrite the SiYuan log entry):
- `POC` is reserved for a PoC **explicitly linked from the advisory's `references`**.
- Reproduction steps embedded in the advisory `Details` are routed `PROBE` going forward
  (within the 60-minute box). SiYuan's recorded chain completed in minutes — inside that cap — so
  the relabeling does not threaten its admissibility; the existing `route=POC` entry stays as-is.
- Canonical operator artifact per candidate: `runs/rd/precheck/<ID>/decision.md`.
- The isolated executor is cleared to run position 2+ manual admissibility under the frozen protocol
  without per-candidate Codex review, until the queue is frozen or a frozen stopping condition fires.

Operator copy (non-tracked): `runs/rd/checkpoints/checkpoint-1.md`.

## Checkpoint #2 — 2026-10-02 (screening complete; queue freeze PENDING)

Durable clarification only. **Nothing is frozen by this entry** and it changes no selection state
(not `selection.py`, the pool, any existing log line, or any verdict). Screening reached the frozen
stopping condition — both languages fill 4 primary + 2 reserve — but the ordered queue is **not**
frozen: two position-reached candidates whose TEST route only showed a *parent compile failure*
require supplemental executable (behaviour-flip) confirmation first.

Append-only log at this checkpoint: 49 entries, hash chain intact, tip `f81b5e28…`.
`selection.py status` passes its own `checked()` gate (script + pool sha256 match).

Provisional queue (from `status`; NOT frozen):
- go primary: `GHSA-fq2j-j8hc-8vw8` (siyuan), `GHSA-mr3j-p26x-72x4` (vikunja),
  `GHSA-rmrf-g9r3-73pm` (flagd), `GO-2026-6237` (dhcp); reserve: `GHSA-fwjx-9p69-h25h` (oh-my-posh),
  `GHSA-xghw-p77p-3r7x` (fabric-ca).
- python primary: `GHSA-hx8v-g79f-8w5f` (litellm), `PYSEC-2026-1868` (reflex),
  `GHSA-xmfj-7pp5-fxr6` (llama-stack), `GHSA-5gfj-64gh-mgmw` (agixt); reserve:
  `GHSA-xcw4-53cc-hv32` (mnemosyne), `GHSA-937x-gpqr-72gg` (flask-reuploaded).

### Clarification 1 — TEST whose parent only fails to compile

A regression test that passes at the fix but at the parent **only fails to compile** — because the
test references an API / field / interface the fix introduces — does not by itself establish
executable behaviour truth. The failure proves the symbol is new, not that the vulnerable behaviour
occurred at the parent. Such a candidate needs additional POC/PROBE behaviour confirmation before
the queue is frozen.

Two candidates match this pattern (both route TEST, verdict ACCEPTED, review boundary not reached):
- `GHSA-rmrf-g9r3-73pm` (flagd, go primary #3): parent fails to build with the fix's tests applied
  (`unknown field MaxRequestBodyBytes` / `MaxRequestHeaderBytes` — the limit API is absent at parent).
- `GHSA-xghw-p77p-3r7x` (fabric-ca, go reserve): parent fails to build with the fix's test applied
  (no stubbable connection interface; the escaping check is absent at parent).

DeepSeek is running supplemental executable confirmation on these two. Their existing ACCEPTED
append-only entries are **not** rewritten; the supplemental result is recorded as a checkpoint
artifact, not by re-running `decide`.

### Clarification 2 — rejection terminology (fixed)

- `EXEC_TRUTH_NOT_CONFIRMED`: an experiment/probe actually ran on both revisions within the boundary
  and time box, but the **parent did not show the expected vulnerable effect**, so no base/head flip
  was established (no truth confirmed).
- `EXEC_TRUTH_UNAVAILABLE`: a valid truth experiment **could not be completed at all** — environment,
  dependency, or review-boundary reasons prevented running it.

The existing Open-WebUI verdict (`PYSEC-2026-1729`, python #14 → `EXEC_TRUTH_NOT_CONFIRMED`: probe
ran ~55 min on both sides, parent forwarded zero events, no flip) is correct and is **not changed**.

### Clarification 3 — quota-skipped ACCEPTED is not a rejection

`ACCEPTED` means the candidate met admissibility (executable truth was established). A candidate may
still not enter the queue purely because a frozen CWE-class diversity quota (`per_cwe_class = 2`) was
already full. A quota-skipped ACCEPTED is **not** a rejection. Current quota-skipped ACCEPTED
candidates (reason `CWE_CLASS_QUOTA`, from `status`): `GHSA-5rmx-256w-8mj9` (wg-portal),
`GHSA-w48f-wwwf-f5fr` (pyload), `PYSEC-2026-429` (murano), `PYSEC-2026-1767` (pgadmin4),
`PYSEC-2026-1137` (airflow).

### Clarification 4 — existing logs immutable

- The flagd and fabric-ca `ACCEPTED` log entries are not modified.
- SiYuan's historical `route=POC` entry is not modified (see Checkpoint #1).
- The append-only hash chain is not rewritten. Supplemental confirmation is recorded as a separate
  checkpoint artifact, never by editing or re-deciding an existing entry.

### Gate to queue freeze

The ordered queue is frozen **only if both** supplemental confirmations (flagd, fabric-ca) establish
`Behavior flip established: true`. If either fails, stop and report `SELECTION_DISPOSITION_CONFLICT`
with the original ACCEPTED decision, the supplemental result, the affected queue slot, and the
append-only provenance — do not freeze, re-decide, or auto-promote a quota-skipped candidate.

Operator copy (non-tracked): `runs/rd/checkpoints/checkpoint-2.md`.

## Checkpoint #2 — supplemental confirmation RESULT (2026-10-02)

Both supplemental executable confirmations passed; reviewed artifact-only (no reproduction run by the
reviewer). Existing ACCEPTED entries, SiYuan `route=POC`, and the append-only chain are unchanged
(still 49 entries, tip `f81b5e28…`); no `decide` was run; `selection.py`/pool sha256 unchanged.

| candidate | repo | supplemental route | behaviour flip | probe elapsed | boundary |
|---|---|---|---|---|---|
| `GHSA-rmrf-g9r3-73pm` | open-feature/flagd | PROBE | true (2.1 MB body: parent 200 → fix 413 OFREP / 429 connect; small-body control 200 both) | ~10 min | not reached |
| `GHSA-xghw-p77p-3r7x` | hyperledger/fabric-ca | PROBE | true (same `GetUser("rd*probe")`: parent emits wildcard substring filter, fix emits literal equality filter via `EscapeFilter`) | ~15 min | not reached |

Reviewer verification: provenance matched (script `1837f907…`, pool `a13f8c5f…`, log_head
`f81b5e28…`); only the fix-touched `_test.go` files are dirty in the parent trees (TEST-route
leftovers, within boundary, not used by the probes); the probe harnesses are untracked new files; no
non-test product source modified on either side. Supplemental route PROBE is correct (advisory
references contain no external PoC link).

Operator evidence (non-tracked): `runs/rd/precheck/<ID>/supplemental-confirmation.md` for both IDs.

**Disposition: supplemental confirmation accepted → the queue freeze gate is satisfied.**
