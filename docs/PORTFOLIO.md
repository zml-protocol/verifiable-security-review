# Portfolio Summary

## 30-second summary

I built a reproducible security-review benchmark and hybrid LLM/static-analysis workflow to test
whether correct vulnerability attribution is backed by machine-verifiable evidence. The system
reproduces real Go and Python security fixes, freezes entry/behavior requirements, lets an isolated
agent propose typed evidence hops, verifies those hops with CodeQL-backed providers, and scores the
sealed artifact without exposing the golden truth. The main result was that correct verdicts were
easier than auditable reasoning: RD v2 attributed 3/5 real fixes correctly but produced 0/5 fully
verified chains.

## Security engineering skills demonstrated

### AppSec

- Reviewed real fixes for information disclosure/path handling, authorization, SSRF, resource
  exhaustion, and signature verification weaknesses.
- Separated root cause into claim-specific entry, security behavior, guard/config/dispatch
  qualifiers, and per-revision realizations.
- Built parent/fix regression evidence and exact source anchors rather than accepting diff-level
  plausibility.
- Implemented typed CodeQL verification for data flow, argument binding, field flow, object
  composition, registry dispatch, guard properties, and range elements.

### Pentest / Offensive Security

- Interpreted advisory PoCs and fix diffs, then reduced them to bounded local reproductions.
- Used a fixed `TEST → POC → PROBE` workflow: existing regression test first, advisory-linked PoC
  second, minimal local probe only when necessary.
- Ran identical triggering inputs against vulnerable and fixed revisions and kept benign controls
  where needed.
- Distinguished demonstrated exploit behavior from inferred reachability, unsupported evidence, and
  broad package-level claims.

### General Security Engineering

- Built Python orchestration around Go/Python repositories, Git object-store reads, CodeQL, MCP
  tools, frozen scoring, and JSON/YAML artifacts.
- Added revision-scoped citations, append-only logs, cryptographic seals, hash-bound freezes,
  budget/time guards, and score-before-review workflows.
- Maintained 271 passing tests for isolation, anchors, scoring, provider semantics, chain
  classification, selection, truth matching, and protocol drift.
- Preserved invalid and negative outcomes instead of silently retrying, repairing, or deleting them.

### AI-assisted security

- Used LLM agents for investigation and requirement discovery while keeping truth construction,
  verification, and scoring as separate roles.
- Designed closed verifier feedback that exposes edge status without leaking golden paths.
- Measured hallucination/evidence risk separately from final vulnerability attribution.
- Treated model outputs as untrusted proposals that require typed validation and provenance.

## Results

| Signal | Frozen result | What it means |
|---|---:|---|
| RD v2 entry discovery | **3/5** | Claim-specific input identification remained difficult. |
| RD v2 behavior discovery | **2/5** | Exact deciding statements were harder than relevant-code discovery. |
| RD v2 fully verified chains | **0/5** | The tested workflow did not meet the evidence standard. |
| RD v2 real-fix attribution | **3/5** | A plausible/correct verdict did not guarantee verified reasoning. |
| RD v2 negative false support | **0/2 revisions** | No false support was observed in the single frozen control task. |
| Earlier chain feasibility | **18/30** | Known local evidence contracts could sometimes be realized and verified. |
| RD v3 premeasurement gate | **0 calls / $0** | A contract mismatch stopped the benchmark before invalid measurement. |

These are small descriptive samples, not claims about all repositories or all models.

## What I learned

1. **Correct verdict ≠ auditable reasoning.** Three RD v2 tasks reached correct attribution despite
   wrong or incomplete requirement/evidence artifacts.
2. **Discovering the evidence contract is harder than following one.** When required facts were
   supplied in earlier work, chains were usually much easier to assemble.
3. **Static providers are strong local filters, not universal proof engines.** They safely verified
   scoped relations but retained blind spots around dispatch, binding, and control semantics.
4. **Fail-closed controls matter.** Context leakage, invalid tool inputs, ambiguous truth, and a
   construction/validator mismatch were recorded rather than converted into cleaner scores.
5. **Fresh-fixture isolation is essential.** Development examples, truth authoring, evaluated-agent
   sessions, and scoring need separate roles and immutable boundaries.

## Interview talking points

### Why build this?

Pentesting taught me that “the patch looks right” is not enough. I wanted an automated reviewer to
show the same kind of reproducible evidence I would expect in an AppSec review: a demonstrated
parent/fix flip, an exact security requirement, and a trace I can check.

### Why not just use accuracy?

Accuracy collapses different failure modes. A model can guess the right fix attribution while
citing the wrong entry, the wrong guard, or an unverifiable path. Separating requirement discovery,
evidence realization, and attribution shows whether the answer is actually auditable.

### What failed?

In the fresh RD v2 tranche, entry and behavior discovery were incomplete and the provider could not
verify every required semantic link. The result was 0/5 full chains even though 3/5 attributions
were correct. RD v3 then stopped before measurement on a public-contract/validator mismatch.

### How did you avoid benchmark leakage?

The benchmark constructor and evaluated agent were separate roles. The measured agent received
neutral revision labels and source access but not advisories, canonical vulnerable/fixed roles,
golden requirements, reference chains, scores, or prior fixture transcripts. Results were scored
and committed before qualitative transcript review.

### What would you build next in a production AppSec system?

I would productize the controls rather than chase a higher benchmark score: make the provider's
accepted evidence language executable and public, surface unsupported links to a human reviewer,
keep requirement and attribution confidence separate, and integrate verified artifacts with PR/CI
review. Human escalation should be the default when a chain is incomplete.
