# RD v3 calibration + protocol delta

Status: **DESIGN APPROVED FOR CONSTRUCTION-SPEC FREEZE — non-binding until the complete v3 freeze;
no fixture selection, paid model run, or formal evaluation is authorized by this document.**

This document proposes the final, bounded follow-up to RD v2. It does not amend, rescore, or
reinterpret RD v2. The v2 protocol, truth, runs, result JSON, and report remain immutable.

## 1. Decision and terminal condition

RD v2 is a valid measurement. It did not demonstrate verified-reasoning capability under the
tested agent/provider treatment: A entry was 3/5, A behavior was 2/5, B full chain was 0/5, and C
real-claim attribution was 3/5. The purpose of v3 is not to make those five fixtures pass. It is to
test, on evaluation-fresh fixtures, whether four narrowly scoped changes generalize:

1. synthetic calibration for the existing strict A schema;
2. generic provider coverage work plus a pre-run reference-realizability gate;
3. harness-owned B partial checkpoints;
4. separation of security-effect attribution from CWE-label agreement.

v3 may proceed beyond the one-shot synthetic gate only if all three conditions hold:

1. the A held-out conformance gate in §3.3 passes;
2. the provider held-out challenge contains no false edge reported as `VERIFIED`;
3. no infrastructure or protocol failure remains unresolved after its pre-frozen infrastructure-only
   retry, if any.

Provider `PARTIAL` and `UNSUPPORTED` outcomes are valid calibration results, not gate failures. The
project ends under either branch below:

- Any condition above fails: publish the specific `A_CALIBRATION_FAILED`, `UNSAFE_PROVIDER`, or
  `CALIBRATION_INVALID` status, do not run fresh fixtures, and close the project.
- The gate passes: freeze the full protocol, run one fresh formal tranche, score and report it, and
  close the project regardless of the model result.

There is no v4 route, no success-triggered extra sample, and no post-result provider repair. Pure
infrastructure failures may be repaired only under a pre-registered, fail-before-interaction rule;
they may not change any model-facing or scored intervention.

## 2. What remains unchanged from v2

Unless this delta explicitly says otherwise, v3 inherits v2:

- the definitions of entry, behavior, `present`, `absent`, and absent context;
- the qualifier kinds `guard`, `config`, and `dispatch_target`; `transform` remains outside the
  primary truth vocabulary;
- the anchor resolver, matcher, statement-granularity requirement, revision mapping, immutable A
  snapshot, and checked-before-submit B rule;
- neutral source access with no advisory, commit identity, canonical revision role, truth, golden,
  reference path, or score exposure;
- closed verifier feedback and the rule that only `VERIFIED` edges form a chain;
- independent truth adjudication, distractors, immutable author truth after a judge sees it, and
  score-before-transcript inspection;
- valid/infra-invalid classification, retry limits, isolation, provenance, seals, cost accounting,
  and fail-closed scoring;
- descriptive reporting with Wilson intervals and no success threshold on the small formal sample.

In particular, v3 adds no qualifier taxonomy, matcher, requirement kind, or chain semantics. The
five v2 real fixtures and their negative control are retired from generalization evidence.

## 3. Change A — synthetic schema calibration

### 3.1 Purpose

Calibration teaches and tests the public representation contract, not fixture answers. It targets
the four observed translation failures without weakening exact scoring:

1. choose the first claim-specific repository value, not a more upstream request object or field
   declaration;
2. choose the decision point that permits/refuses the effect, not merely a value computed for that
   decision;
3. represent a changed statement that exists in both revisions as `present` in both, with distinct
   anchors/content;
4. distinguish `absent/context` from `present/anchor` and use a complete statement rather than a
   subexpression or enclosing function declaration.

Formal v3 A scoring remains exact against fresh frozen truth. No partial credit from the synthetic
gate changes the formal metric.

### 3.2 Development corpus

The development corpus is synthetic, fixture-free, and versioned separately. It contains at least
one Go and one Python case for each boundary family above. Names, effects, control flow, and code
shapes must not be copied from any v2 fixture. Development cases may be inspected and iterated on.

The final A prompt may include concise worked examples derived only from this development corpus.
Those examples and every prompt edit are part of the v3 treatment and must freeze before the
held-out gate.

### 3.3 Held-out conformance corpus

The held-out corpus uses different programs, identifiers, effects, and syntax shapes. Its fixed
size is 20 cases: two languages × five cells (the four families above, with statement granularity
split from state encoding) × two cases. Before development, freeze its construction specification,
cell counts, generator inputs or independent-curator instructions, and commitment procedure. The
prompt/provider implementer must not see instantiated held-out source or labels during development.
After the treatment freezes, instantiate or unseal the corpus exactly once, record source, labels,
order, and hashes, and run it without repair. This ordering prevents both prompt tuning to held-out
answers and post-prompt tailoring of the challenge.

The one-shot gate is:

- at least 16/20 cases have both entry and behavior exactly correct;
- every language × boundary-family cell has at least one exact success;
- zero accepted anchors are a forbidden subexpression, field declaration standing in for a runtime
  entry, or enclosing function standing in for a parameter/statement;
- no changed statement that is present in both revisions is encoded as absent in either revision;
- all harness/seal/isolation invariants pass.

These numbers and guards are final. They cannot be changed after corpus construction or held-out
results. Failure yields `A_CALIBRATION_FAILED` and triggers the terminal condition in §1.

## 4. Change B1 — generic provider extension

### 4.1 Boundary

Provider work may improve implementation coverage only within already-admitted relation semantics.
The v2 failures motivate four generic coverage targets:

- a scalar definition consumed by a guard predicate;
- lexical guard/control use, but only where an existing relation already entails it;
- an ordinary direct or same-object call binding;
- callback/function-value binding.

Before implementation, each target must be mapped in writing to an existing frozen relation and its
endpoint roles. If no existing relation entails the proposed edge, it remains a blind spot. v3 does
not create a new relation or silently broaden an old truth condition. In particular, generic lexical
control dependency is out of scope if it cannot be represented without new chain semantics.

No v2 repository, anchor, hop, query row, or transcript may appear in provider development or gate
data. After the provider is frozen, v2 may be run only as an engineering regression suite; those
results are never v3 evidence.

### 4.2 Development and held-out challenge

For each eligible target, create synthetic development cases and a separately authored held-out
challenge. Each set must contain at least two true edges and two near-miss false edges per applicable
language. Near misses should include misleading name similarity, wrong receiver/object, unbound
callbacks, and predicates that are nearby but do not consume/control the claimed value. As with A,
the held-out construction specification and commitment mechanism freeze before development, while
instantiated source and labels remain unavailable to the query implementer until the provider freezes.

The held-out provider gate is deterministic and one-shot:

- any false edge reported `VERIFIED` is `UNSAFE_PROVIDER` and stops v3;
- tool/query failure is `INCONCLUSIVE_TOOL_FAILURE` and follows a pre-frozen infrastructure-only
  retry rule;
- a relation implementation is `SUPPORTED` only if every core true held-out case verifies and no
  false case verifies;
- missing true cases with zero false verification produce `PARTIAL`, with exact blind spots frozen;
- an eligible target with no verified true case remains `UNSUPPORTED`.

`PARTIAL` and `UNSUPPORTED` do not by themselves stop v3. They constrain which fresh reference
obligations can be proved and are visible in the system-level metrics below.

## 5. Change B2 — reference-realizability gate and two-level metrics

### 5.1 Order and anti-selection rule

The exact provider, relation table, connector, and analysis pipeline freeze before any fresh formal
fixture is selected or inspected. Fresh fixtures are selected without reading provider support.

For each selected fixture, the author first completes execution truth, requirement truth, anchor
self-review, and reference evidence. The reference audit then runs before any judge sees the truth.
`REFERENCE_INVALID` may be corrected at this point, but a blind or unrealizable disposition may not
change truth, trigger replacement, or reopen provider work. The judges then receive the frozen author
bundle. After admissible truth freezes, the exact audit reruns; any unexplained disposition/hash drift
is a protocol failure.

Reference disposition never causes fixture replacement. Every admissible fresh fixture remains in A,
C, and system-level reporting. This prevents selection for provider-friendly tasks.

### 5.2 Disposition

The audit is performed per revision and per required chain/qualifier obligation, then summarized per
task:

- `REFERENCE_FULLY_VERIFIED`: every applicable reference obligation forms a complete chain under
  the exact frozen provider;
- `PROVIDER_BLIND`: a semantic reference chain exists, but at least one required edge or attachment
  cannot be verified by the frozen provider;
- `REFERENCE_UNREALIZABLE`: the truth-defined forward entry→behavior chain does not exist,
  independently of provider coverage;
- `REFERENCE_INVALID`: author evidence is incomplete or internally inconsistent; this is a harness
  failure, not a model outcome.

Only `REFERENCE_FULLY_VERIFIED` tasks enter the conditional agent B denominator.

### 5.3 Required B reports

v3 reports both views; neither may replace the other:

1. **Conditional agent capability:** agent-graph `FULL_CHAIN` and correct verified implementation
   among `REFERENCE_FULLY_VERIFIED` tasks.
2. **End-to-end system capability:** agent-graph `FULL_CHAIN` and correct verified implementation
   among all admissible real tasks, with `PROVIDER_BLIND` and `REFERENCE_UNREALIZABLE` retained as
   explicit non-success dispositions.

The two B outcomes retain their v2 meanings. Agent-graph `FULL_CHAIN` asks whether the graph closes
under the agent's own locked A requirements. Correct verified implementation additionally requires
the complete A requirement specification to match admissible truth. A full chain under wrong A
anchors is never reported as correct verified reasoning.

It also reports reference coverage before model execution: counts of fully verified, provider-blind,
and unrealizable tasks and obligations. This prevents denominator improvement from being mistaken
for system improvement.

The conditional denominator has a frozen interpretation rule:

- `n = 0`: report raw `0/0`, no rate or interval, status
  `B_CONDITIONAL_NOT_ESTIMABLE`;
- `n = 1–2`: report raw `k/n`, no percentage capability conclusion, status
  `B_CONDITIONAL_UNDERPOWERED`;
- `n >= 3`: report `k/n`, rate, and Wilson 95% interval.

This is an interpretation rule, not a formal-run success threshold. The end-to-end system rate and
Wilson interval are always reported over all admissible real tasks, irrespective of conditional n.

## 6. Change B3 — automatic partial checkpoint

The harness, not the model, owns an append-only checkpoint log. Before returning each `check_hop`
result, it atomically records:

- monotonic event number and prior-event hash;
- exact proposed hop and its resolved verifier state;
- A seal, task/revision identity, provider/relation-table hashes, and current graph-state hash;
- tool-call provenance and phase-relative timestamp.

Rejected structural proposals are logged as events but never enter the graph. The current graph is
deterministically reconstructable from the event log. At B termination the harness materializes and
seals a `partial_checkpoint` containing the last reconstructable graph, even when the model never
calls final submit. A successful `submit_evidence` separately seals the model's final selection.

Primary semantics do not change:

- only a valid final submission can earn `FULL_CHAIN` in the conditional agent metric;
- a partial checkpoint is never promoted to a final submission;
- a missing final submit remains observed agent behavior and is not retried.

Secondary checkpoint metrics are pre-registered: verified edge count, largest connected component,
longest verified entry prefix, longest verified terminal suffix, terminal reach, qualifier
attachments, last successful event, and whether the final checkpoint already contained a full chain.

If B terminates validly without a final submission, the runner seals `B_TERMINAL_NO_SUBMIT` plus the
checkpoint and still proceeds to C. It does not rerun B. A temporary account-level quota may pause
the batch before C, but resuming C after reset is continuation of the same task, not a B retry.

## 7. Change C — effect attribution before CWE taxonomy

### 7.1 Agent-facing claim

Every v3 task has a frozen, neutral `effect_claim` describing the attacker-controlled input class
and security-relevant effect in plain language. A and B see this claim and do not see a CWE id or CWE
name. The claim must be written and independently adjudicated with the fixture truth before model
execution. It must describe the effect without disclosing the fixing revision, advisory identity,
exact anchor, or evidence path.

Negative controls use the same effect-claim schema. Mechanically substituted candidate effects come
from a pre-frozen plain-language library corresponding to the existing CWE substitution list; they
must pass the same three-way NOT_SUPPORTED rule. No control is manually chosen for difficulty.

### 7.2 C1 — primary effect attribution

C1 receives the sealed A artifact and the sealed final-B artifact or explicit
`B_TERMINAL_NO_SUBMIT` checkpoint. It has no source or verifier tools. It labels each revision
`SUPPORTED`, `NOT_SUPPORTED`, or `INDETERMINATE`; the existing deterministic mapping derives
`FIX_IMPLICATED`, `CHANGE_IMPLICATED`, `PRE_EXISTING`, `NOT_SUPPORTED`, or `UNDETERMINED`.

C1 is the primary C metric. Its result locks before the taxonomy task is enabled; the target label
remains hidden from the model throughout C2.

A valid C-phase refusal, timeout after usable interaction, budget stop, malformed/non-submission, or
failure to call a locking tool is observed model behavior and is never retried. If C1 does not lock,
record `C1_MISSING` and `C2_NOT_REACHED`; the primary C observation is missing/incorrect according to
the frozen scorer, but the absence alone is not a harness failure. If C1 locks and C2 does not,
retain and score C1, record `C2_MISSING`, and do not reinterpret the absence as
`NO_CONFIDENT_CWE`. Bad seals, foreign tools, phase-order violations, or lost artifacts after a
successful lock remain fail-closed harness failures.

### 7.3 C2 — secondary frozen-label agreement

After C1 locks, C2 receives the same plain-language effect claim and sealed artifacts, but **not**
the fixture's frozen/advisory CWE label. Its output must take exactly one of two forms: a ranked list
of one to three CWE ids, or `NO_CONFIDENT_CWE`. Either form may carry an unscored rationale. C2
cannot revise C1. Each task manifest contains a hidden frozen taxonomy comparison target: the
selected advisory/claim CWE for a real task and the mechanically substituted CWE for a negative
control. The scorer alone compares a ranked list with that hidden target. Reporting is descriptive:

- top-1 and top-3 agreement with the frozen claim label;
- explicit alternative labels proposed by the model;
- `NO_CONFIDENT_CWE` rate.

This is **frozen-label agreement**, not objective taxonomy accuracy. v3 introduces no new CWE truth
adjudication tree. C1 and C2 must not be combined into one correctness score.

Because v3 removes CWE labels from A/B/C1 and changes the C construct, raw v2 and v3 C rates are not
the same metric and must not be pooled or presented as a causal improvement.

## 8. Fresh-fixture plan

### 8.1 Freshness boundary

Formal v3 fixtures must not have appeared in:

- any v2 real/control task or inadmissibility review;
- A or provider synthetic development/calibration;
- prior provider experiments, regression fixtures, blog examples, or fieldwork analysis;
- any prompt or transcript used to design this delta.

“Fresh” means fresh to this experimental workflow; it does not claim absence from model pretraining.
Repositories already used by those artifacts are excluded to reduce near-duplicate adaptation.

### 8.2 Bounded tranche

The fixed plan is three Go and three Python primaries, plus three reserves per language, for a
maximum of twelve manual admissibility reviews and a target real N of six. Reuse the already-hashed
OSV snapshot and the old mechanical filters. Before provider development, freeze the target/reserve
counts, exclusion-list construction, ordering algorithm, and a procedure for obtaining the seed
without exposing the resulting queue to the implementer. The seed itself must come from an
independent commitment or nonce revealed only after the provider and prompt freeze; it may not be
chosen by trying candidate orders. Only after the synthetic gate passes may the queue be materialized
and committed with its seed, exclusions, and append-only selection log. Do not open a new snapshot or
expand the window merely to reach N.

The existing TEST → POC → PROBE boundary, repository/CWE quotas, truth adjudication, reserve order,
and reduce-N/no-backfill rule remain. Exhausted reserves reduce N. Reference disposition never
consumes a reserve.

The target and reserve counts above are final and freeze before the new seed is generated. The
formal result is a first/final fresh treatment tranche, remains descriptive even if all six
primaries are admitted, and is not a population benchmark.

## 9. Execution and budget topology

### 9.1 Exact agent configuration

v3 uses the exact v2 agent configuration:

- model `claude-sonnet-5`;
- effort `high`;
- Claude Code CLI `2.1.280`;
- the same isolation, source-tool, call-cap, retry, and no-memory semantics except where this delta
  explicitly changes checkpointing and C.

There is no automatic model or CLI fallback. If the exact configuration is unavailable before the
first held-out model call, no held-out case is opened; execution stops and returns for an explicit
project decision.

### 9.2 Per-task envelope

Every held-out A task and every formal task keeps the v2 incremental/cumulative accounting:

| phase | incremental budget | session cumulative cap | wall time |
|---|---:|---:|---:|
| A | `$3` | `$3` | 1200s |
| B | `+$3` | `$6` | 1800s |
| C1 + C2 combined | `+$1` | `$7` | 600s combined |

C1 must submit and lock before C2 is enabled. Whether C uses one CLI invocation or a C1 invocation
followed by a resume, C2 receives neither a new dollar allocation nor a reset 600-second clock.
Both substeps together remain inside the single cumulative `$7` task cap. CLI terminal overshoot,
if any, is recorded honestly; these are launch/reservation ceilings, not provider-enforced billing
hard caps.

### 9.3 Three separate ledgers

Development/plumbing-pilot spending is recorded separately and completes before any held-out corpus
is instantiated or unsealed. It is not charged to either measurement ceiling and requires explicit
user authorization before any paid model call.

The held-out A measurement has an independent `$60` launch ceiling: 20 A-only fresh sessions ×
`$3`. It cannot borrow from, lend to, or be adjusted based on the formal pool. It requires explicit
user authorization before the corpus is instantiated or unsealed. If the held-out gate fails, no
formal pool starts.

The formal budget unit is a formal task, not a real fixture. Every qualified negative control runs
the same complete A→B→C task and consumes the same maximum `$7` reservation. Freeze the formula:

```text
formal_task_count =
    realized_real_tasks
    + qualified_negative_control_tasks

formal_launch_ceiling =
    $7 × formal_task_count
```

The real target is six, reduce-N may make `realized_real_tasks <= 6`, and each real fixture may
produce at most one qualified negative control. Qualification is determined only by the frozen
truth/adjudication procedure. It never depends on model behavior, remaining budget, reference
disposition, or expected difficulty. At target N=6, the exact formal ceiling is `$42` with no
controls and at most `$84` with six controls; reduce-N lowers both values mechanically.

After all real/control truth freezes and before the first formal model call, write the exact task
count, full real/control task list, order, and derived ceiling into the run manifest and bind them in
the protocol freeze. Runner and scorer must verify that every manifest task reaches exactly one
terminal scored task record and that none is dropped, reordered, or conditionally skipped. Only
pre-registered infrastructure-invalid attempts may precede that terminal record. Such retries do
not create a new task reservation or enlarge either measurement ceiling; the inherited v2
retry/accounting rules apply.

### 9.4 User spending authorization

User authorization is an external spending control, not a scientific outcome or a substitute for
the two measurement ceilings. It is requested in three stages:

1. a separate development/pilot authorization before any paid development call;
2. the full `$60` held-out authorization before held-out instantiation/unsealing;
3. after real/control truth and `formal_task_count` freeze, authorization for the entire derived
   formal envelope (`$7 × formal_task_count`) before any formal task starts.

Before stage 3, report development/pilot actual spend, held-out actual spend, the frozen formal
ceiling, and the remaining worst-case exposure. Earlier v2 authorization does not carry forward.
No protocol-level overall dollar amount is pre-registered.

If the remaining authorization is smaller than the entire frozen formal envelope, start no formal
task and record `FORMAL_NOT_STARTED_BUDGET_AUTHORIZATION`. Do not drop controls, languages, or other
tasks; do not run a prefix and seek further authorization based on its results. This is an
administrative non-start, not a model result, and the research project remains scientifically
incomplete until the complete frozen tranche is either authorized and run or explicitly abandoned.

## 10. Metrics and interpretation

Formal v3 reports:

- the unchanged strict A entry/behavior/qualifier precision and recall;
- provider reference coverage before agent execution;
- conditional B agent-graph full-chain and correct-verified rates on
  `REFERENCE_FULLY_VERIFIED` tasks, subject to the §5.3 denominator status;
- end-to-end B agent-graph full-chain and correct-verified rates on all real tasks;
- pre-registered partial-checkpoint diagnostics;
- C1 effect-attribution accuracy on real claims and false-supported rate on controls;
- C2 frozen-label agreement as a separate secondary result;
- explicit `C1_MISSING`, `C2_NOT_REACHED`, and `C2_MISSING` counts;
- failure categories that distinguish A error, agent graph gap, provider blind, reference
  unrealizable, no final B submit, and C1 attribution error.

The report must preserve the distinction exposed by v2: a correct C1 attribution without correct A
and a full verified B artifact is a correct answer without verified reasoning. It is not upgraded to
end-to-end success.

v2 and v3 are reported side by side, never pooled. Since v3 changes the prompt calibration,
provider coverage, reference denominator, checkpoint behavior, claim representation, and fixture
sample, any difference is a new-treatment result, not an attribution to one component.

## 11. Build, freeze, and run order

1. Review and accept this delta; no new intervention or methodological parameter opens afterward.
2. Freeze synthetic construction specifications, development data, hidden-challenge commitment
   procedures, selection parameters/seed procedure, and all generation provenance.
3. Obtain a separate development/pilot spending authorization. Develop A examples, provider changes,
   checkpoint/C1/C2 plumbing, and the scorer using development data only.
4. Complete a fixture-free plumbing pilot covering checkpoints, C1→C2 locking, missing-final-B
   continuation, isolation, accounting, and fail-closed scorer behavior.
5. Freeze prompts, provider, harness, scorer, exact model/CLI, budgets, timeouts, and pilot. Confirm
   the exact agent configuration is available and obtain the full `$60` held-out authorization;
   only then instantiate/unseal and run the held-out A and provider gates once.
6. If the gate fails, publish the failure and stop under §1.
7. Reveal the independent selection seed, materialize and freeze exclusions/queue, then select fresh
   fixtures. For each, complete author truth/reference self-review, audit without replacement, then
   independent adjudication and freeze.
8. Rerun the exact reference audit on frozen truth; lock denominators and task order without
   replacement. Freeze qualified controls, the full formal manifest, exact formal launch ceiling,
   truth, analyses, and task order; report the three ledgers and obtain authorization for the whole
   formal envelope.
9. If full authorization is absent, record the administrative non-start and run nothing. Otherwise
   run the complete fresh formal tranche once; commit scores before transcript inspection; audit and
   report.
10. Write the final project synthesis and close the research program regardless of the valid formal
    model result.

## 12. Explicit non-goals

v3 does not add:

- a new qualifier taxonomy, matcher, resolver, or requirement schema;
- a new relation vocabulary or changed chain semantics;
- fixture-specific provider queries or examples derived from v2 code;
- a feedback-arm experiment, ablation tree, model comparison, or product benchmark;
- post-result threshold changes, fixture replacement, provider tuning, or another experimental round.

The intended final answer is bounded: after schema calibration and provider-safe measurement repair,
can the same class of agent discover requirements, build a fully verified chain where the frozen
provider can realize one, and attribute a plain-language security effect on evaluation-fresh code?
