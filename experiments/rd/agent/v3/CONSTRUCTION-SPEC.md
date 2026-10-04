# RD v3 synthetic construction specification

Status: **construction inputs freeze when `construction_freeze.py verify` succeeds.** This freeze
authorizes no paid model call and contains no instantiated held-out case.

The controlling design is `../V3-PROTOCOL-DELTA.md`, approved by
`../V3-FINAL-REVIEW.md`. This specification instantiates only the pre-model construction step. If
this document conflicts with the approved delta, the delta wins and construction stops.

## 1. Frozen inputs and separation

The construction freeze binds:

- this specification and the construction validator;
- `a-development.yaml`: ten inspectable A development cases;
- `a-heldout-spec.yaml`: the exact 20-case hidden A matrix and curator rules, without instances;
- `provider-development.yaml`: inspectable generic provider cases inside existing semantics;
- `provider-heldout-spec.yaml`: hidden provider challenge counts and curator rules, without
  instances;
- `selection-seed-spec.yaml`: the fresh-queue nonce and derivation procedure;
- the approved v3 delta/review and the existing frozen definitions/vocabulary they inherit.

Development source and truth are public to the implementer. Held-out source and labels do not exist
in this tree at construction freeze. They are instantiated only after the complete prompt/provider/
harness treatment freezes, by a curator that did not implement that treatment. The curator must
follow the frozen specs, record every instance and label, and commit a content-hash manifest before
the first held-out model or provider evaluation. No instance can be edited or replaced afterward.

The implementer may inspect the committed held-out instances only after the treatment freeze. At
that point inspection cannot reopen code or prompt development; it is limited to executing the
one-shot gate and auditing provenance.

## 2. A calibration cells

There are five cells in each of Go and Python. A held-out case belongs to exactly one cell even when
its program contains secondary lures.

| cell | required distinction | critical failure |
|---|---|---|
| `claim_specific_entry` | first repository value carrying the attacker input named by the claim, rather than an upstream request/container or later derivative | field declaration, whole request/container, or later derived value selected as entry |
| `decision_point` | statement that permits/refuses the security effect, rather than a value computed for that statement | comparison/computation selected instead of the deciding guard |
| `changed_present_both` | one changed statement exists in both revisions and must be encoded `present`/`present` with revision-specific anchors | either revision encoded `absent` |
| `absent_context` | a statement exists in one revision and its absence in the other is represented by the exact controlled/supplied context | invented absent anchor, wrong context, or `present` used for nonexistent code |
| `statement_granularity` | complete statement anchor rather than a subexpression, declaration field, parameter line, or enclosing function | any forbidden coarse/fine anchor accepted |

The ten development cases provide one case per language/cell. They are examples and prompt
development material, never gate observations.

The hidden A matrix has two independent cases per language/cell: 2 languages × 5 cells × 2 = 20.
Each instance must:

- use a different package/module name, identifiers, effect, and primary syntax shape from the
  development case in the same cell;
- contain at least one plausible lure representing the cell's forbidden choice;
- provide two syntactically valid revisions and exact full-statement truth anchors/contexts;
- keep entry and behavior independently identifiable from the plain-language effect claim;
- contain no name, comment, path, or literal copied from an RD v2 fixture;
- contain no CWE id/name, advisory id, commit metadata, or canonical vuln/fixed label.

The curator labels exact entry and behavior realizations before any held-out run. The 16/20 gate and
all structural/cell guards are those in the approved delta; construction cannot alter them.

## 3. Provider construction boundary

Every provider target was checked against the already-admitted relation semantics before case
construction:

| v2-motivated target | eligibility | frozen reason |
|---|---|---|
| scalar definition consumed directly by a guard predicate | ineligible | `def_use` destinations are later definitions or call arguments/calls, not predicates |
| generic lexical control dependency | ineligible | no admitted relation entails predicate→controlled-statement flow |
| Python ordinary typed attribute-method dispatch | eligible as `python/call_typed_attribute` | existing truth is call `a.b.m(...)` → function body it can invoke |
| Go direct-call argument binding | eligible as `go/argument_binding` | existing truth is call argument i → runtime callee parameter i |
| Go callback/function-value argument binding | eligible as `go/argument_binding` | AB-1 already declares reachable function values true, though the v2 verifier may miss them |
| generic same-object connector expansion | ineligible | v2 connector support is Go-specific; adding new Python/object semantics would change chain semantics |

Ineligible targets stay documented blind spots and receive no implementation or held-out cases.
Eligible work may change only verifier/query coverage, node extraction, or analysis plumbing inside
the stated truth. It may not broaden endpoint roles or relation truth.

`provider-development.yaml` contains two true and two near-miss false edges for each eligible row.
The hidden provider challenge independently contains the same 2-positive/2-negative minimum per
eligible row. False cases cover wrong callee/receiver, wrong argument index, and an unreachable
callback as applicable. The construction curator must not use development identifiers or copy its
control-flow layout.

The hidden provider gate is deterministic. Any false→`VERIFIED` result is unsafe and stops v3.
Missed true edges produce `PARTIAL`/`UNSUPPORTED` under the approved delta and do not cause the
curator to replace a case.

## 4. Held-out commitment procedure

After treatment freeze and before any held-out execution:

1. A non-implementing curator receives only the frozen construction specs, definitions, and public
   schema—not development outputs or v2 fixture code.
2. The curator creates all A and provider held-out instances in a repository-external temporary
   directory, labels them, and runs syntax/anchor validation.
3. A materialization tool copies the complete batch into the future held-out directory in one
   operation and writes a manifest containing every relative path, SHA-256, case id, language/cell
   allocation, and a Merkle-style aggregate hash over sorted `(path, sha256)` pairs.
4. Source, labels, manifest, curator identity/type, independence attestation, treatment-freeze hash,
   and construction-freeze hash are committed together before execution.
5. Any missing cell, duplicate case, validation failure, hash drift, or post-commit edit is
   `CALIBRATION_INVALID`; there is no case substitution or regeneration.

The future materialization tool may implement these already-frozen checks, but it cannot change the
case matrix, eligibility mapping, labels, or gate.

## 5. Fresh-selection seed procedure

Selection parameters are already fixed at three Go and three Python primaries plus three reserves
per language. The implementer freezes provider/prompt/harness before learning the seed.

After the synthetic gate passes, the user or another non-implementing operator supplies exactly one
uniformly random 32-byte nonce as 64 lowercase hexadecimal characters and attests that it was not
chosen by comparing candidate orders. No second nonce is accepted. The selection seed is:

```text
sha256("rd-v3-selection\0" || treatment_freeze_sha256 || "\0" || nonce_bytes)
```

The full hexadecimal digest is interpreted as an unsigned big-endian integer by the deterministic
ordering implementation. The nonce, attestation, treatment freeze hash, derived seed, exclusions,
queue, and selection-script hash are committed before manual review. A malformed nonce or any
attempt to derive multiple queues is `SELECTION_PROTOCOL_INVALID`.

## 6. Construction freeze and next authority boundary

`construction_freeze.py write` is allowed only with a clean tracked tree at the reviewed design
commit. It validates development schemas, cell/target counts, syntax, exact anchor lines, forbidden
v2 identifiers, and all bound input hashes. `verify` recomputes the same checks and hashes.

After this freeze, the next allowed work is unpaid implementation or an explicit request for the
separate development/pilot spending authorization. No held-out instance, fresh candidate, or paid
model session may be opened merely because construction verification succeeds.
