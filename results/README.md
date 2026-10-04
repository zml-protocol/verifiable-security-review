# Results Index

Frozen result files are preserved as originally scored. This index identifies the shortest path
through them; it does not replace or reinterpret the underlying reports.

## Start here

1. **Fresh requirement-discovery measurement** — [`rd-agent-v2.md`](rd-agent-v2.md) and
   [`rd-agent-v2.json`](rd-agent-v2.json)
   - 5 real fixes + 1 negative-control task
   - entry 3/5, behavior 2/5, full verified chain 0/5, real attribution 3/5
2. **Architecture feasibility** — [`chain-replication.md`](chain-replication.md) and
   [`chain-replication.json`](chain-replication.json)
   - 18/30 fully verified local chains when the evidence contract was already known
3. **Fail-closed terminal result** — [`rd-agent-v3.md`](rd-agent-v3.md) and
   [`rd-agent-v3.json`](rd-agent-v3.json)
   - premeasurement `CALIBRATION_INVALID`; 0 model calls and $0 spend
4. **Provider conformance** — [`rd-conformance.md`](rd-conformance.md) and
   [`rd-conformance.json`](rd-conformance.json)
   - 7 supported and 2 partial providers; no false conformance edge was verified

## Compressed history

[`docs/RESULTS.md`](../docs/RESULTS.md) explains how the 1B, prompt A/B, Spike P, P-Hybrid,
chain-replication, P-extension, and RD stages led to one another. Use it before opening the
individual historical files in this directory.

## Integrity note

The JSON outputs are the frozen machine-readable records. Human-readable reports add post-score
diagnosis without changing those scores. Negative, ambiguous, invalid, and infrastructure outcomes
remain present by design.
