# RD truth tooling (drafts for §15.10 steps 4–5)

Generic, fixture-free tooling for the phases that follow the fixture queue freeze. None of these
files is part of the frozen selection machinery; they are **drafts pending Codex review** and
must not be used to write truth before the queue is frozen (PREREGISTRATION.md §15.1, §15.10).

| file | implements | notes |
|---|---|---|
| `negative_control.py` | §15.6: pick the first three substitution candidates for a fixture CWE from the frozen list L, cyclically and skipping the same CWE class | class map imported from the frozen `selection.py` |
| `agreement.py` | §15.1 item 5: three-way agreement, distractor outcomes, one- and two-sided missing items, equivalence by full requirement identity, ambiguity burden, `INCOMPLETE_TRUTH_SPEC`, and both vocabulary blind-spot buckets (author-side and missing-side) | anchor identity takes the frozen matcher once wired; production fails loud without it |
| `distractors.py` | §15.1 item 4: near-move, qualifier kind swap and one-revision state flip | anchors/contexts come from callbacks supplied at fixture time; the module refuses to fabricate them, never targets a kind outside the frozen vocabulary, and returns no distractors for an unsupported author item |
| `templates.py` | §15.1 item 4: empty fixture-truth and adjudication-sheet generator | per-revision present/absent schema (present→anchor, absent→context, base/head independent); explicit `NA`/`truth_inadmissible`; the four truth statuses stay independent; writes no golden and refuses to write under `results/` |
| `matcher.py` (+ `goresolver/`, `matcher-provenance.json`) | §15.1 item 5: the single frozen `anchor_identity` matcher | canonical **syntax-node identity** `(language, revision, path, node_type, structural_path, content_digest)`; native parsers (Python `ast`; Go `go/parser` mode 0). Identical-text nodes at different positions differ; the same node reformatted matches; a different revision differs. Bound once (no arbitrary `module:function`); provenance/hash mismatch fails loud. |
| `freeze.py` (+ `truth-tooling-freeze.json`) | §15: truth-tooling production freeze | binds+pins the frozen matcher, vocabulary (9 relations; `guard/config/dispatch_target`; `transform` blind spot), provider-support, the frozen queue + hash, and all tool source hashes; re-checks gate/queue/tool-rule invariants; guards the designated truth-write area (excludes `results/` and the selection tree). Writes no fixture truth. |
| `anchor-matcher-proposal.md` | §15.1 item 5 (history) | the original proposal; now **implemented** in `matcher.py` (see its status header) |

Self-tests:

```bash
uv run python experiments/rd/truth/negative_control.py --self-test
uv run python experiments/rd/truth/agreement.py --self-test
uv run python experiments/rd/truth/distractors.py --self-test
```

Input shapes for `agreement.py` are documented in its docstring; they are drafts and will be frozen
together with the step-4 procedure. Nothing here reads a fixture, an advisory or the selection log,
and nothing writes under `results/`.

**Freeze-time requirement:** when these tools are frozen (after the candidate queue freeze),
`--anchor-matcher` must be bound to the single frozen matcher identity with its hash checked — not
to any caller-supplied callable — so the equivalence rule is the scorer's rule and nothing else.
