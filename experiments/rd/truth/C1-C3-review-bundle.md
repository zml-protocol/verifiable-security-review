# C.1–C.3 review bundle (truth-tooling freeze; pending Codex review before C.4)

Fixture-independent truth infrastructure only. **No fixture-specific truth was written and no
primary fixture's source or advisory was opened** (proof at the bottom). All tests green; invariant
suite is 0-xfail.

## C.1 — frozen production anchor matcher

- Implementation: `experiments/rd/truth/matcher.py` (`node_identity`) + Go helper
  `experiments/rd/truth/goresolver/node_id.go` (+ `go.mod`).
- Identity: canonical **syntax-node identity**
  `(language, revision, path, node_type, structural_path, content_digest)`.
  - `structural_path` = root→node child-ordinal path → distinguishes two identical-text nodes at
    different positions; formatting-invariant (comments off; positions excluded).
  - NOT narrow `(revision,path,sha256)`, NOT line-overlap.
  - One abstract interface, two native parsers: Python stdlib `ast`; Go `go/parser` (mode 0) run
    with the bundled `go1.26.8`.
- Provenance: `experiments/rd/truth/matcher-provenance.json` pins matcher file sha256, Go helper +
  go.mod sha256, Go version, Python version, and the identity tuple.
- Enforcement (wired into `agreement.py` via `matcher.load_frozen_matcher`): callers cannot pass an
  arbitrary `module:function`; a provenance/hash mismatch fails loud; the exact-tuple stand-in lives
  only in self-tests, never as a production fallback.
- Tests (`tests/test_rd_matcher.py`, Go cases run on the bundled toolchain):
  identical-text/different-position → differ (py+go); same node reformatted → equal (py+go);
  different revision → differ; changed matcher file → refused; changed Go helper → refused; foreign
  spec → refused; `None` anchor → fail loud.

## C.2 — Phase A full-payload sealing

- `experiments/rd/agent/phases.py`: `RequirementItem` now carries the full structured `payload`;
  the A seal covers `public()` including payload. The strict-xfail is **gone**.
- Payload sealed per kind: entry/behavior anchor; qualifier subject anchor + expected semantic
  field + per-revision present→anchor / absent→context state; rationale (**in the seal** — B/C
  cannot rewrite A's reasoning); and any `UNSUPPORTED_REQUIREMENT_TYPE` proposal (sealed as part of
  the artifact, never dropped).
- Caller payloads are deep-copied on `add`; B cannot modify A; C consumes frozen A and frozen B.
- Tests (`tests/test_rd_agent.py`): seal covers payload + unsupported proposal; post-lock mutation
  of entry anchor / absent context / qualifier expected field / unsupported proposal / rationale /
  add-item / remove-item each caught by phase C; external caller dict isolated. 0 xfail.

## C.3 — truth-tooling production freeze

- `experiments/rd/truth/freeze.py` + manifest `experiments/rd/truth/truth-tooling-freeze.json`.
- Binds/pins: frozen matcher; vocabulary (9 relation groups; qualifiers `guard/config/dispatch_target`;
  `transform` blind spot; entry/behavior fixed); provider-support table; frozen selection queue
  (`results/rd-queue.yaml`, `queue_sha256 58d9f18a`, log head `f81b5e28`, tip `b91d9751`, n go/python
  = 6/6); and all truth-tooling source hashes.
- Re-checks (fail loud): matcher provenance; vocabulary gate READY; queue hash == the log's `queue`
  entry; the reviewed tools' behavioural self-tests (agreement, distractors, negative_control); the
  four truth statuses stay independent; `NA` is a structural string, not 0.
- Write-area guard: fixture truth may be written only under `experiments/rd/truth/fixtures/`; the
  guard refuses `results/`, the selection run tree, and unsafe ids.
- Tests (`tests/test_rd_freeze.py`): verify passes; drifted tool source → refused; drifted matcher →
  refused; write-area guard excludes protected trees.

## Hard-gate test summary

Full suite: **225 passed, 0 xfailed** (`uv run python -m pytest -q`). RD-specific modules:
`tests/test_rd_matcher.py`, `tests/test_rd_agent.py`, `tests/test_rd_freeze.py`,
plus unchanged `tests/test_rd_selection.py`, `tests/test_rd_boundary.py`, `tests/test_rd_conformance.py`.

## Proof no fixture-specific truth was opened

- `experiments/rd/truth/fixtures/` does not exist; no fixture-truth / golden artifact was created.
- No advisory or primary fixture source was read in this phase; `matcher.py` self-tests and all
  hard-gate tests use synthetic snippets only, and the freeze explicitly refuses to call the matcher
  against a queue fixture.
- Selection state untouched: `results/rd-queue.yaml`, the pool, `selection.py`, and the append-only
  log are unchanged by C.1–C.3 (log tip still `b91d9751`).

## Not done (awaiting Codex approval, then C.4)

No fixture truth. After approval, C.4 starts strictly in frozen-queue order (Go: SiYuan, Vikunja,
flagd, DHCP; Python: LiteLLM, Reflex, Llama Stack, AGiXT), each via executable→author→two
adjudications→admissibility gate→freeze, and the evaluated RD agent sees no fixture until all primary
fixture truth is frozen.

## Freeze provenance

- Approved by Codex; committed atomically as `3b474e86e3988e9d583e1f1c0023921db3a235a9`
  (`rd: freeze truth infrastructure before fixture truth`).
- This commit hash is the outer provenance record; it is deliberately NOT written into
  `truth-tooling-freeze.json` (that manifest pins content hashes only, no self-reference).
- Working tree after the freeze commit: clean except the unrelated untracked `blog/`.
