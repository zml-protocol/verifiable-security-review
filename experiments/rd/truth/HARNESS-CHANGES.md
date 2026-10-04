# Truth-tooling harness changes (post-freeze)

Changes to the frozen truth tooling after the C.1–C.3 freeze (`3b474e86`). Each must be a pure
implementation/wiring fix under the frozen harness-change rule — never a change to the identity
tuple, the matcher, the qualifier/relation definitions, or any measurement standard, and never tuned
to a specific fixture's results. Recorded for Codex review before use.

## 2026-10-02 — HC-1: anchor→node-ref resolver (wiring bug fix), pending Codex review

**Classification: wiring implementation incomplete.** C.1 froze the matcher
(`matcher.node_identity`, input = a node-ref with language/path/revision/source + column span) and
the truth tooling froze the anchor schema (`{file, start_line, end_line, expression}`) separately.
Nothing connected them: `agreement.py` loaded the matcher, but the anchors reaching it could not be
consumed. The two frozen ends literally could not call each other. This is the one case that
qualifies as a wiring bug; a fresh fixture merely being "hard to express" does **not** qualify going
forward.

HC-1 was completed in one shot (Codex "complete HC-1 in one shot"), closing all four gaps so no
HC-2 is needed for fresh-fixture expressiveness. From here, a fresh fixture that is merely hard to
express (matcher can't express an equivalence, a relation/qualifier doesn't fit) is recorded as a
measurement result, never a tooling change — only a pure implementation bug may be touched.

**What changed (additive; no frozen tool semantics edited):**
- `resolver.py` — strict/generic `{file,line-range,expression}+revision+language+source → node-ref →
  matcher.node_identity`. Unique match within the range (0/>1 → fail loud); sub-line fragment → fail
  loud; **only leading/trailing indentation is tolerated, internal text is exact** (string-literal /
  token whitespace is program semantics, not formatting). The frozen matcher alone decides identity.
  `resolve_doc` pre-resolves a doc's anchors so the **unchanged** `agreement.check` runs with an
  identity passthrough — no `agreement.py`/`matcher.py` source edited.
- `anchor_machinery.py` — the fixture-independent distractor callbacks `distractors.py` requires
  (`relocate` near-move / `context_for` / `present_for` / `rebuild`). Generic, repository-revision
  source + frozen resolver/matcher, fail loud; a near-move target must exist unchanged in BOTH
  revisions and resolve to a different node. No fixture symbol/path/line; distractor semantics
  unchanged.
- `revision_map.py` — author truth uses canonical `vuln`/`fixed`; mapped ONCE per fixture to outward
  `revision_A`/`revision_B` by parity of `sha256(seed:fixture_id)`; second remap refused. The seed is
  now **bound to the frozen pool provenance** (manifest `selection.pool_sha256` + `seed`): a changed
  pool or seed fails loud instead of silently remapping. `make_source_provider` keys source by the
  mapped canonical role, so a fixed-side anchor always resolves against the fixed source (label and
  source cannot desync).
- `freeze.py` / `truth-tooling-freeze.json` — `TOOL_SOURCES` now also pins `anchor_machinery.py`,
  `revision_map.py`, `resolver.py` and **`freeze.py` itself** (so the verifier can't be swapped
  silently); the manifest pins a new `selection` block (pool sha256 + seed).
- Synthetic tests: `tests/test_rd_resolver.py`, `tests/test_rd_revision_map.py`,
  `tests/test_rd_anchor_machinery.py`.

**What was NOT changed:** the identity tuple, the matcher, `agreement.py`/`distractors.py`/
`vocabulary.py` sources, the qualifier/relation vocabulary, or any admissibility/scoring rule. No
fixture tuning; all tests synthetic.

**Provenance:** the HC-1 implementation commit hash is recorded in the follow-up commit below (not
written into the manifest, to avoid a self-reference loop). Full suite after the change:
249 passed, 0 xfailed.

- HC-1 implementation commit: `301e93de4d3ebacc89d9616866cb9e171aefbc10`
