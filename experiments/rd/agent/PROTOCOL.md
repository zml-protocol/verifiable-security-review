# RD agent protocol v2

Status: **RD v2 operational protocol; binding when `freeze.json` verifies**.

This document operationalizes PREREGISTRATION.md §15.5–§15.10 step 6. It does not change the frozen
truth vocabulary, matcher, provider queries, candidate set, or fixture truth.

## Experimental unit and order

One task is one claim over one frozen fixture and its two seed-mapped revisions. Each task gets one
fresh Claude conversation containing three sequential turns, A then B then C. No conversation,
working directory, MCP state, or auto-memory is reused across tasks.

There are six measured tasks: five real claims and the one valid §15.6 negative control. Each runs
once. Their author-side mapping is in `manifest.yaml`; the measured order is the fixed
seed-20261003 shuffle in `order.txt`. Task ids are opaque. The agent never receives fixture ids,
advisory ids, roles (real/control), canonical revision roles, commits, commit messages, dates,
advisory text, execution truth, requirement truth, reference evidence, or scores.

The agent-facing claim is the frozen neutral template:

> Evaluate this claim: in `<package>`, attacker-controlled input may lead to `<CWE name>`.
> Compare revision_A and revision_B, determine what must be proved to assess the claim, and finally
> decide how the change between the revisions relates to that behavior.

## Agent and isolation

- Agent: `claude-sonnet-5`, effort `high`.
- Required Claude Code CLI: `2.1.280`.
- Each task uses an empty temporary working directory outside every git repository.
- CLI isolation: `--tools "" --strict-mcp-config --allowedTools mcp__secreview
  --setting-sources ""`. A random explicit session id is created for A; B and C resume that same
  conversation sequentially. The temporary CLI project/session directory is copied into the run
  audit record and then removed. No branch or fork is used.
- Incremental budgets and timeouts: A = $3 / 1200 s; B = $3 / 1800 s; C = $1 / 600 s. Because
  Claude Code accounts resumed conversations cumulatively, the corresponding CLI session caps are
  $3 / $6 / $7. The six-task launch ceiling is $42. Every started phase reserves its incremental
  allocation; no launch may cross the ceiling. A conversation's latest cumulative report is counted
  once (not once per resumed phase).
- A task is attempted at most three times, and only an infrastructure-invalid task may be retried.
  Failed attempts are retained. A timeout after any successful tool call, a budget stop, refusal,
  malformed/absent submission, or failure to finish is valid agent behavior and is never rerun.
  Network/API/CLI startup failure before a usable tool interaction is infrastructure-invalid.
- Measured tasks run only from a clean, committed tree whose protocol freeze verifies.
- Before any measured attempt directory is created, the runner must confirm local Claude login,
  reach `api.anthropic.com` within ten seconds, and launch the exact dynamic stdio MCP process used
  by the run, complete its handshake, and observe the exact phase-A tool names. Failure aborts the
  batch without consuming a measured attempt. The check invokes no model and exposes no source.

## Shared code-reading surface

A and B receive the same read-only tools: `get_task`, `list_files`, `read_code`,
`search_code`, `find_symbol`, `changed_files`, `diff_file`, and `map_location`.

Only tracked blobs at the two commits are readable. Git metadata, commit identities/messages and
denied advisory/release-note paths are unavailable. Returned revisions are always
`revision_A`/`revision_B`. Limits are 200 code lines per read, 50 search hits, 300 listed paths,
and 400 displayed diff lines. A has at most 60 non-submission tool calls; B has at most 40. A
limit rejection states only that the limit is exhausted.

## A — requirement discovery

A sees the task, the frozen entry/behavior/absent-context definitions, the admissible qualifier
kinds (`guard`, `config`, `dispatch_target`), and the requirement schema. It does not see the
relation vocabulary, provider-support table, CodeQL, B feedback, or any truth artifact.

A submits exactly one entry slot, one behavior slot, and zero to six qualifier proposals. Each slot
has both outward revisions and uses exactly one of:

- `{state: present, anchor: {file,start_line,end_line,expression}}`
- `{state: absent, context: {file,start_line,end_line,expression}}`

Every item must be present in at least one revision. Qualifiers use the frozen kind-specific fields.
At most two of the six proposals may instead be `UNSUPPORTED_REQUIREMENT_TYPE`; they carry a note
and no scored slot. Anchors must resolve uniquely at statement granularity through the frozen
resolver/matcher. A successful `submit_requirements` is allowed once and locks a byte-canonical
snapshot plus SHA-256. Up to three rejected submission attempts are allowed; feedback is limited to
schema, cap, path, and anchor-resolution errors.

## B — verified realization

B receives the immutable A snapshot and, for the first time, the admissible relation vocabulary for
the task language. It may continue ordinary code reading. It cannot add, remove, or alter any A
item. It may record one free-text `requirement_doubt`, which is unscored.

B may call `check_hop` at most 18 times. A hop is one relation and two exact endpoints in one
revision. Feedback is deliberately closed:

- `VERIFIED`: “confirmed”;
- `UNVERIFIED`: “not confirmed”;
- `UNSUPPORTED`: “unable to confirm”;
- structural input errors identify only the schema/anchor/node-kind problem.

No query row, suggested endpoint, next hop, golden, reference path, provider calibration blind spot,
or truth label is returned. `SUPPORTED` and `PARTIAL` provider pairs are VERIFIED-eligible;
unknown, `UNSUPPORTED`, `NON_CONFORMANT`, and explicit `unsupported` hops always return
UNSUPPORTED. The verifier queries and relation semantics are the already-frozen ones.

The final graph contains at most 12 distinct hops, and every submitted hop must have been checked
byte-identically in this B turn. A successful `submit_evidence` is allowed once and locks the hops,
their verifier states, the doubt, the A seal, and a B seal. There are at most three rejected final
submission attempts.

For each revision whose locked entry or behavior is absent, no chain is required. Otherwise the
scorer classifies the VERIFIED-edge graph from the locked entry to the locked behavior using the
frozen §12 path rules. Locked present qualifiers must be attached to that same graph: each present
anchor slot of each locked qualifier must resolve, under some frozen relation role, to a node on the
same verified entry→behavior path; absent slots add no attachment obligation. A missing attachment
is a qualifier gap. Unsupported/UNVERIFIED hops remain audit evidence but never become edges. A
reference evidence is scored separately to distinguish `PROVIDER_BLIND` and the directionality
case below; it never changes the agent graph or fixture inclusion.

The pre-agent §15.3 reference audit also records `REFERENCE_UNREALIZABLE` when the already-frozen
truth anchors have no forward semantic entry→behavior chain at all, independently of provider
coverage. This late audit result does not reopen judge-seen truth and does not remove the fixture:
A and C remain scored, and the preregistered all-real-fixture B rate still includes it. A secondary
B rate on the reference-realizable subset is reported so the interface defect is not attributed to
the model or provider. In RD v2 this applies to LiteLLM: request safety validation evaluates the
frozen behavior before routing later performs the frozen `user_config` entry extraction.

## C — attribution

C receives only the frozen A and B snapshots and the neutral claim. It has no code-reading,
mapping, diff, or verifier tool. Conversation context from its own A/B turns remains available.
It submits one of `SUPPORTED`, `NOT_SUPPORTED`, or `INDETERMINATE` for each outward revision,
plus an unscored rationale. A successful submission locks once.

The scorer maps outward labels back through the frozen seed mapping and derives:

- vuln SUPPORTED / fixed NOT_SUPPORTED → `FIX_IMPLICATED`;
- vuln NOT_SUPPORTED / fixed SUPPORTED → `CHANGE_IMPLICATED`;
- both SUPPORTED → `PRE_EXISTING`;
- both NOT_SUPPORTED → `NOT_SUPPORTED`;
- every other pair → `UNDETERMINED`.

Real claims expect `FIX_IMPLICATED`; the frozen DHCP/CWE-352 control expects
`NOT_SUPPORTED`. This permits the preregistered “A wrong but C guessed correctly” category while
still preventing C from changing or supplementing A/B.

## Validity, scoring and inspection order

The runner records CLI/model identity, task and phase, budgets/timeouts, commits/tree ids, outward
mapping, all protocol/tool hashes, A/B seals, phase costs, tool counts, environment isolation, and
raw event/error logs. The scorer fails closed on missing locks, changed hashes, foreign tools,
mapping drift, seal mismatch, or analysis provenance mismatch.

After all reachable tasks terminate, scoring runs and its result is committed before any human
opens measured agent transcripts. Main metrics and failure categories are exactly §15.8. Wilson
95% intervals accompany proportions. The secondary reference-realizable B rate described above is
reported alongside, never in place of, the all-fixture rate. The Mnemosyne negative-control
scope-invalid batch is absent from the task manifest and denominator.

No success/failure threshold is set. With five real claims and one weak negative control, RD v2 is
descriptive: harness invariant failure yields `HARNESS_INVALID`; otherwise the report presents the
pre-registered metrics without routing the project on a model-performance cutoff.

## Plumbing pilot

The pilot uses a synthetic repository made solely for this purpose, never an evaluation fixture. It
must exercise:

1. neutral A/B mapping and all read tools;
2. successful A locking plus rejection of post-lock mutation;
3. B relation disclosure only after A, the 18-call gate, all four closed feedback classes, checked-
   before-submit enforcement, B locking, and A-seal verification;
4. C's lack of read/verifier tools and immutable A/B consumption;
5. sequential Claude resume, empty-cwd/no-memory isolation, cost/timeout metadata, and cleanup;
6. scorer determinism and fail-closed tamper tests.

Pilot transcripts and outcomes are non-measured. Plumbing defects may be repaired before the final
freeze, with each repair recorded. After the pilot passes, protocol/prompt/schema/runner/scorer/tool
hashes and the synthetic source commits are written to `freeze.json`; any later change requires a
new protocol version.

RD v2 inherits RD v1 pilot attempt 4 because its measured prompts, tools, schemas, conversation
flow, limits, and scorer are unchanged. Its only runner changes occur before a measured attempt or
make an already-infrastructure-invalid reason more specific. The inherited pilot artifact is pinned
again by the v2 freeze, and deterministic tests cover the new gates.

### Pilot repair log

- Attempt 1 passed the A/B/C functional checks. Its audit exposed that Claude Code reports resumed
  session cost cumulatively: the original runner summed A, B and C cumulative totals and passed
  incremental caps to all three invocations. Before freeze, accounting was corrected to count the
  latest cumulative total once and pass cumulative CLI caps $3/$6/$7 for incremental allocations
  $3/$3/$1. Attempt 2 confirmed that repair. A later whole-suite import-order audit then hardened
  the scorer/runner against collision with older experiments' same-named modules. Attempt 3 then
  exposed a pilot-only provenance bug after the synthetic source bytes changed: an existing analysis
  was reused without checking its embedded commit, so phase B's MCP failed before exposing any tool.
  The runner now classifies a missing expected tool surface before any interaction as
  `INFRA_INVALID`, and pilot preparation rebuilds any commit-mismatched analysis. Attempt 4 is the
  infrastructure retry and final pilot used by the freeze. Earlier attempts remain retained.

## RD v1 invalid launch and v2 recovery

The first formal v1 operator launch was mistakenly executed inside a sandbox with restricted DNS.
Task-03 attempts 1–3 each returned an API `EAI_AGAIN` before tokens, cost, or usable tool
interaction; the operator then interrupted task-04 attempt 1 while diagnosing the common fault.
The v1 scorer result was committed as `HARNESS_INVALID` at `6241243` before its transcripts were
opened. Failed attempts remain in the run audit directory and are not relabelled or reused.

RD v2 is a new protocol version rather than a reset of those attempts. It does not alter any
agent-facing or scored scientific input. It adds the pre-attempt infrastructure gate above and
checks explicit API errors before generic missing-tool-surface classification. The v1 invalid result
is itself a v2 freeze input. At the time of this amendment, v1 had incurred $0 and no model emitted
an evaluation response, so v2 retains the original $42 measured launch ceiling.
