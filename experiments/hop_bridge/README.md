# §14 P-extension: bridge verifiers (provider-only)

Can three relations, implementing four semantic steps, connect the long-frozen Spike P source
endpoints (the real entry) to the §12 local subgraph with hops the frozen verifiers judge
VERIFIED? No LLM. Protocol: PREREGISTRATION.md §14.

| semantic step | hop relation | languages |
|---|---|---|
| def-use continuation | `def_use` | Go, Python |
| parameter/argument binding + cross-function call | `argument_binding` | Go |
| collection -> range element binding | `range_element` | Go |

- `relations.yaml`: truth conditions, node kinds, verifiers (`queries/{go,python}/`, CodeQL 2.27.1).
  Relations are the frozen P-Hybrid-1 ones plus these three, judged by `spike.hops`.
- `sets/{dev,cal,current}.yaml` + `truth/`: dev (synthetic, `fixtures/_bridgedev`), cal (held out,
  `fixtures/_bridgecal`), current (the three current fixtures, 95 hops). `run` never reads truth.
- `entry_anchors.yaml`: the Spike P source endpoints as node identities. Terminals and qualifiers
  are §12's (`experiments/hop_chain/anchors.yaml`).

```
uv run python fixtures/_bridgedev/build.py && uv run python fixtures/_bridgecal/build.py
uv run python experiments/hop_bridge/bridge.py check --set dev|cal|current
uv run python experiments/hop_bridge/bridge.py run --set dev|cal|current   # cal/current: once, clean tree
uv run python experiments/hop_bridge/bridge.py score --set dev|cal|current # results/p-extension-<set>.json
uv run python experiments/hop_bridge/bridge.py chain    # results/p-extension-chain.json
uv run python experiments/hop_bridge/bridge.py decide   # results/p-extension-decision.json
```

The current set reuses the P-Hybrid-2 CodeQL databases (`runs/hop_propose/analysis/`) and the frozen
P-Hybrid-1 outputs (`experiments/hop_propose/frozen/`, checked against their manifest).

Scores are per verifier implementation (`codeql/go/def_use`, `codeql/python/def_use`, ...; the
relation-level rollup is report-only). `decide` routes, first match wins:
UNSAFE -> INCONCLUSIVE_TOOL_FAILURE -> CALIBRATION_BLIND (a §14 verifier BLIND on held-out cal)
-> CAPABILITY_GAPS -> LOOP_CLOSED.
