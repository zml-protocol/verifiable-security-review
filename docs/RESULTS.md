# Results: From Vulnerability Reproduction to Verifiable Review

This page compresses the experiment history into the engineering decisions it supported. Frozen
reports and scores remain unchanged under [`results/`](../results/); this is a navigation layer, not
a rescore.

| Stage | Question | Frozen result | Decision |
|---|---|---|---|
| Executable truth: Authlib, Caddy, File Browser | Can the claimed security behavior be reproduced across two revisions? | Parent/head probes established concrete differential behavior and controls on Python and Go fixtures. | Use behavioral truth as the base layer; do not treat a diff as proof. |
| 1B evidence contract | Can an agent support an attribution with all required citations? | Attribution was **98.1%**, but evidence-complete + correct was **25%**; one malformed regex was misclassified as a harness error. | Freeze the failure, fix the tool classification, and test whether clearer path instructions help. |
| v2 path-prompt A/B | Does explicitly asking for path citations solve evidence completeness? | Control **13.8%**, treatment **21.2%**; **+7.5 pp**, below both preregistered thresholds. | Prompting alone was insufficient; move path evidence into a typed interface. |
| Spike P | Can a general provider recover the full source-to-sink path directly? | Frozen CodeQL queries recovered **0** complete evaluation paths and exposed dispatch/container/guard gaps. | Replace monolithic reachability with small, typed, independently verifiable hops. |
| P-Hybrid-1 | Can typed single-hop claims be checked safely? | All five scoped relation types were `SUPPORTED`; no false edge was verified in the frozen calibration/evaluation challenges. | Let the agent propose hops and the provider verify each hop. |
| P-Hybrid-2 | Does one round of verifier feedback improve golden-hop coverage? | Coverage stayed **66.7% → 66.7%**; treatment-control gain **0.0 pp**; final status `FAIL`. R016 also exposed an ambiguous “one-step composition” truth boundary. | Verification filters proposals but cannot reveal omitted evidence; keep the ambiguous label frozen. |
| Chain replication (§12) | Can an agent assemble complete local verified chains without feedback? | **18/30** full chains: Authlib **10/10**, Caddy **3/10**, File Browser **5/10**. | Architecture is locally feasible; missing guards and entry choices remain the main gaps. |
| Completeness repair (§13) | Does a one-bit “incomplete” signal repair chains? | Too few eligible pairs: Caddy **2**, File Browser **5**; status `INCONCLUSIVE_OPPORTUNITY`. With the evidence contract supplied, initial chains were already full in 28/30 and 25/30 cases. | The hard problem is discovering required evidence, not merely retrying a known contract. |
| P-extension (§14) | Can generic provider extensions connect real entries to the local chains? | Six author-known revision chains closed; one Caddy-head hop depended on a truth interpretation later disputed by blind review. | Demonstrated provider feasibility, not autonomous discovery; retire the three development fixtures. |
| RD definition/conformance | Is the evidence vocabulary decidable and do providers fail safely? | Nine relation groups admitted; 7 providers `SUPPORTED`, 2 `PARTIAL`; **0/22** false conformance cases verified. | Freeze the vocabulary and move to fresh real fixes. |
| RD truth construction | Can fresh real fixes meet executable and independently adjudicated truth requirements? | Planned 8, realized **5** admissible fixtures (3 Go, 2 Python); ambiguous/unexpressible cases and exhausted reserves reduced N without backfill. | Preserve quality gates instead of filling the sample with weaker truth. |
| RD v2 fresh measurement | Can the agent discover requirements, build verified evidence, and attribute the fix? | Entry **3/5**, behavior **2/5**, full chain **0/5**, real attribution **3/5**, negative false support **0/2**; `harness_ok=true`. | Valid fail: keep the framework, do not claim verified-reasoning capability. |
| RD v3 held-out gate | Did a bounded calibration treatment qualify for one final fresh tranche? | `CALIBRATION_INVALID` before execution: public curator contract and frozen validator disagreed on an accepted Go statement type. **0 model calls, $0**. | Fail closed, do not repair/resample, do not start the formal tranche, close the project. |

## The main result

The project moved from “can an agent give the right answer?” to “can a reviewer reconstruct and
machine-check why that answer should be trusted?” RD v2 showed the distinction clearly:

```text
correct real-fix attribution: 3/5
fully verified evidence chain: 0/5
```

This does not prove that LLM-assisted security review is ineffective. It shows that the tested
workflow did not meet a strict evidence standard, and that attribution accuracy alone would have
hidden the gap.

## What is primary versus supporting evidence?

- **Primary fresh result:** RD v2.
- **Supporting architecture evidence:** P-Hybrid-1, chain replication, and P-extension.
- **Protocol-quality result:** RD v3 fail-closed termination.
- **Historical development evidence:** 1B, prompt A/B, Spike P, P-Hybrid-2, and completeness repair.

For the exact denominators, confidence intervals, failure categories, and provenance, read:

- [`rd-agent-v2.md`](../results/rd-agent-v2.md)
- [`chain-replication.md`](../results/chain-replication.md)
- [`rd-agent-v3.md`](../results/rd-agent-v3.md)
- [`rd-conformance.md`](../results/rd-conformance.md)
