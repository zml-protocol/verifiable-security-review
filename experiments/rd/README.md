# RD: requirement discovery on fresh fixtures (PREREGISTRATION.md §15)

> **Project status:** complete. RD v2 is the final valid model measurement; RD v3 terminated
> fail-closed before model execution. Start with [`docs/RESULTS.md`](../../docs/RESULTS.md),
> [`results/rd-agent-v2.md`](../../results/rd-agent-v2.md), and
> [`results/rd-agent-v3.md`](../../results/rd-agent-v3.md). The construction notes below preserve
> the historical state at the time this phase began.

The charter is frozen (`3fcdf0d`). This directory holds the pieces built under it, in the order of
§15.10.

- `osv-snapshot.json`: the frozen OSV Go/PyPI snapshot the candidate pool will be built from (the
  zips stay in `.cache/osv/`; no advisory has been looked at yet).
- `definitions.yaml` (draft): operational definitions for the 8 RD relations, entry, behavior,
  absent context and the 4 qualifier kinds, with numbered boundary rules. Shown to adjudicators
  verbatim.
- `boundary/`: synthetic boundary cases (`fixtures/_rdbound/build.py` builds the modules).
  - `relation_cases.yaml` / `requirement_cases.yaml`: what adjudicators label (opaque ids, no labels);
  - `relation_labels.yaml` / `requirement_labels.yaml`: the author's labels, each naming the rule it tests;
  - `gen_cases.py`: writes all four (anchors are located from the module text, never typed);
  - `check.py`: anchors resolve, payloads are well formed, labels name defined rules, coverage.

```
uv run python fixtures/_rdbound/build.py
uv run python experiments/rd/boundary/gen_cases.py
uv run python experiments/rd/boundary/check.py
```

- `conformance.py`: the verifier-conformance gate (frozen `977b591`; result `0f7e0b1`, gate READY).
  `results/rd-vocabulary.json` holds the two frozen tables (truth vocabulary, provider support) and
  the gate; `gate_ready()` must be true before the OSV snapshot is opened.

Historical status at this document's original checkpoint: the truth infrastructure was complete
(decidability rounds 1 and 2, conformance), and fixture selection was next. The later selection,
truth, agent, and terminal records remain in this directory and under `results/`.
