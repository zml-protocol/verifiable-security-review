# Proposal → IMPLEMENTED: the single anchor_identity matcher (PREREGISTRATION.md §15.1 item 5)

Status update (C.1): **implemented and frozen, pending Codex review of the C.1–C.3 bundle.** The
matcher now lives in `experiments/rd/truth/matcher.py` (`node_identity`), pinned by
`experiments/rd/truth/matcher-provenance.json`; the enforcement below is wired into `agreement.py`
via `matcher.load_frozen_matcher`. The narrow/wide tuples were NOT used; identity is a canonical
syntax-node identity `(language, revision, path, node_type, structural_path, content_digest)` built
on native parsers (Python stdlib `ast`; Go `go/parser` via the pinned `goresolver/node_id.go`). The
text below is the original proposal, retained for provenance.

---

Status: **proposal, pending Codex review. Not implemented.** No code in this repo binds a frozen
matcher yet. This note records (a) the enforcement mechanism the freeze requires and (b) the
candidate identity to bind to, so the binding can be reviewed *before* it is written and before the
candidate queue is frozen. Nothing here changes vocabulary, relations, or any scorer rule.

## Why this is still open

`experiments/rd/truth/agreement.py` already refuses to run without a matcher (`load_matcher` →
`SystemExit` when `--anchor-matcher` is absent) and uses a diagnostic `exact_identity` stand-in in
`--self-test` only. But `load_matcher(spec)` today imports **whatever** `module:function` the caller
passes. That is exactly the caller-substitutable matcher the freeze forbids: the equivalence rule
used to decide "same requirement" across adjudicators must be the scorer's one rule and nothing the
operator can swap at run time.

No frozen matcher identity (module:function + file hash) has ever been recorded anywhere in the
tree (grep for `FROZEN_MATCHER`, `matcher_sha`, etc. is empty). So this is a first-record decision,
which is design-touching and belongs to Codex, not to be written unilaterally mid-selection.

## Enforcement mechanism proposed (to wire at freeze time, after the queue freeze)

When the truth tools are frozen, replace the free `load_matcher(spec)` with a bound check:

1. A single module-level constant names the frozen matcher: `FROZEN_MATCHER = ("<module>:<function>", "<file-sha256>")`.
2. At load, the tool:
   - refuses any `--anchor-matcher` value **other than** the recorded `module:function` (no
     substitution: an operator cannot point it at a different callable);
   - imports that function, resolves the file that defines it, and recomputes that file's sha256;
   - **fails loud** (`SystemExit`, provenance mismatch) if the recomputed hash ≠ the recorded hash.
3. The same bound matcher is the one the RD scorer uses, so author/judge equivalence and scoring
   equivalence are provably the same function.

This is enforcement only; it adds no new qualifier, relation, or rule.

## Candidate identity to bind to (for Codex to approve)

The anchor machinery already exists and is the natural, already-implemented matcher:

- module: `src/spike/anchors.py` (current file sha256 `0f8b3a9f76f04fa78c1ffc3ee65bd298fa3b838c15a4ada2a97e0f0511b80049`, at HEAD `882e294`)
- the `Anchor` model is `ConfigDict(frozen=True)` with fields
  `(id, revision, path, start_line, end_line, sha256)`, where `sha256` is `_sha` over the
  whitespace-normalised (`_norm`) located window.

What decides "same requirement anchor" between two adjudicators is still open. Two tuple forms over
the existing `Anchor` fields were considered and **both rejected as the final identity** (Codex, r1):

| option | tuple | why it is not the final identity |
|---|---|---|
| narrow | `(revision, path, sha256)` | **collides**: two syntactically identical statements in one file at the same revision (e.g. two separate `return None`) hash the same and would be merged into one node |
| wide | `(revision, path, start_line, end_line, sha256)` | avoids that collision, but is **over-strict**: two adjudicators quoting different spans of the same statement would be judged non-equivalent |

Direction for the real binding (Codex, r1): the canonical identity should be a **syntax-node
identity** — a stable node identifier from a frozen resolver (e.g. a tree-sitter node), with a
content hash as a secondary guard — rather than letting a line span or a quote hash *define*
semantic identity. No wrapper exists yet and none should be written as a narrow/wide tuple. When the
binding is implemented (after queue freeze), the resolver that produces the node identity is what
gets pinned by `module:function` + file hash, and adding it to `anchors.py` must be the last edit
before the hash is recorded.

## Do not, until approved + queue frozen

- Do not edit `agreement.py`'s `load_matcher` to the bound form yet.
- Do not add `anchor_identity` to `anchors.py` yet (adding it changes that file's sha256, which the
  binding will then pin — so it must be the *last* edit before the freeze record is written).
- Do not use any truth tool to write fixture truth before the queue is frozen.
