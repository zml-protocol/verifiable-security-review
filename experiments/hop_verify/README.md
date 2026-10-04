# P-Hybrid-1: provider hop verification (PREREGISTRATION.md §10)

Frozen single hops (true ones split from golden locations, false ones generated
by four mutation rules) checked one at a time by generic, relation-specific
CodeQL verifiers. No LLM.

    uv run python fixtures/_hopdev/build.py && uv run python fixtures/_hopcal/build.py
    uv run python experiments/hop_verify/verify.py check --set dev|cal|eval   # before the freeze
    uv run python experiments/hop_verify/verify.py run --set cal              # once, after the freeze
    uv run python experiments/hop_verify/verify.py score --set cal
    uv run python experiments/hop_verify/verify.py run --set eval             # once, after cal is committed
    uv run python experiments/hop_verify/verify.py score --set eval
    uv run python experiments/hop_verify/verify.py decide

- `relations.yaml`: truth condition, endpoint node kinds and verifier per relation.
- `queries/{python,go}/`: `Shapes.ql` (every node kind, closed-world shape check) and one
  verifier per relation; no fixture symbol (tested).
- `sets/*.yaml`: hops as a provider or a future agent sees them (no truth).
- `truth/*.yaml`: labels, mutation kinds and falsity reasons, read by `score` only.
- Runs go to `runs/hop_verify/<set>/` (databases, raw rows, `states.json`); scores to
  `results/p-hybrid-1-*.json`.
