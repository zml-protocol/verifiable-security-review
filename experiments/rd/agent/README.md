# RD agent protocol (step 6)

This directory implements the frozen-candidate RD A → B → C experiment described in
`PREREGISTRATION.md` §15 and operationalized by `PROTOCOL.md`.

The binding file set, analyses, reference audit and post-repair pilot are pinned by `freeze.json`.
Formal execution is allowed only when `freeze.py verify` succeeds from a clean tracked tree.

## Components

| file | purpose |
|---|---|
| `manifest.yaml`, `order.txt` | six opaque tasks and the seeded one-run order |
| `schema.py` | exact public A/B/C schemas and SHA-256 seals |
| `source.py` | neutral, git-metadata-free code reading shared only by A and B |
| `session.py`, `mcp_server.py` | phase-specific tool surfaces, caps, closed feedback and locking |
| `analysis.py` | apply the already-frozen CodeQL relations and same-object query to fresh fixtures |
| `graph.py` | recompute B verdicts and apply the frozen §12 path rules |
| `reference.py` | classify author evidence as fully verified, provider blind, or unrealizable |
| `run.py` | one fresh Claude conversation per task, sequential A/B/C resume, retries and budgets |
| `score.py` | pre-transcript scoring, Wilson intervals and harness fail-closed checks |
| `pilot.py`, `pilot/` | non-measured synthetic repository and sequential conversation pilot |
| `freeze.py` | pin protocol, prompts, dependencies, truth/reference inputs, analyses and pilot |

## Pre-freeze sequence

```bash
UV_CACHE_DIR=/tmp/secreview-uv-cache uv run pytest -q tests/test_rd_*.py
UV_CACHE_DIR=/tmp/secreview-uv-cache uv run python experiments/rd/agent/analysis.py
UV_CACHE_DIR=/tmp/secreview-uv-cache uv run python experiments/rd/agent/reference.py
UV_CACHE_DIR=/tmp/secreview-uv-cache uv run python experiments/rd/agent/pilot.py prepare
UV_CACHE_DIR=/tmp/secreview-uv-cache uv run python experiments/rd/agent/pilot.py run
UV_CACHE_DIR=/tmp/secreview-uv-cache uv run python experiments/rd/agent/freeze.py write
```

`pilot.py run` is the only pre-freeze command above that invokes Claude. The pilot is synthetic and
unscored. Repairs discovered by it are made before the freeze and the pilot is rerun.

## Formal sequence

Formal tasks refuse a dirty tracked tree, model/CLI drift, missing analysis, freeze drift, failed
Claude authentication, an unreachable Anthropic endpoint, or an unhealthy dynamic MCP handshake.
The infrastructure checks finish before a measured attempt directory is created.

```bash
UV_CACHE_DIR=/tmp/secreview-uv-cache uv run python experiments/rd/agent/freeze.py verify
UV_CACHE_DIR=/tmp/secreview-uv-cache uv run python experiments/rd/agent/run.py --all
UV_CACHE_DIR=/tmp/secreview-uv-cache uv run python experiments/rd/agent/score.py \
  --out results/rd-agent-v2.json
```

Commit `results/rd-agent-v2.json` before opening measured `agent.jsonl` or copied CLI session logs.
Only infrastructure-invalid tasks may restart, at most three total attempts. A valid refusal,
timeout after tool use, budget stop, missing lock, or malformed submission counts as observed agent
behavior and is never rerun.

`rd-v1` is retained as an invalid administrative launch. It ran inside a network-restricted
sandbox: three task-03 starts reached neither the API nor a usable tool interaction, and the
operator stopped task-04 while diagnosing the repeated startup fault. The frozen scorer result is
`results/rd-agent-v1.json` at commit `6241243`; its metrics are not model measurements. RD v2 keeps
the intervention, order, prompts, truth, limits, and $42 measured launch ceiling unchanged, adding
only the fail-before-attempt infrastructure gate and accurate API-error ordering.
