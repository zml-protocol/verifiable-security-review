# RD v3 held-out curator contract

This contract is measurement plumbing for the already-frozen construction rules. It does not
change the 20-case A matrix, provider targets, labels, thresholds, or eligibility semantics.

The curator must not have implemented or inspected the v3 prompt/provider treatment. The curator
receives `CONSTRUCTION-SPEC.md`, `a-heldout-spec.yaml`, `provider-heldout-spec.yaml`, this contract,
and the public A/hop schemas. It must not receive the development instances, v2 fixtures, treatment
transcripts, or fixture-specific failures. It creates the complete batch outside the repository and
reveals it once, only after the user authorizes the full held-out measurement.

## Commitment layout

Materialize one directory containing `commitment.json`, 20 A case YAML files, and three provider
case YAML files. `commitment.json` has:

```json
{
  "schema": "rd-v3-heldout-commitment/v1",
  "treatment_freeze_sha256": "<sha256 of treatment-freeze-v2.json>",
  "construction_freeze_sha256": "<sha256 of construction-freeze-v2.json>",
  "curator": {
    "role": "non_implementing_curator",
    "type": "<human or model/config>",
    "independence_attestation": true
  },
  "a_cases": ["relative/case paths in fixed run order"],
  "provider_cases": ["relative/case paths in fixed target order"],
  "files": {"relative/path": "sha256"},
  "aggregate_sha256": "sha256(canonical JSON of sorted [path, sha256] pairs)"
}
```

Every file in `files` appears exactly once in either `a_cases` or `provider_cases`. Commit the
directory, including the commitment, before running the model or provider. No case may be repaired,
replaced, reordered, or regenerated after commitment.

## A case schema

Each A YAML file has schema `rd-v3-a-heldout-case/v1` and fields:

- `task_id`: unique neutral id;
- `language`: `go` or `python`;
- `cell`: one frozen A cell;
- `package` and neutral `effect_claim`;
- `files`: `revision_A` and `revision_B`, each mapping relative paths to complete source strings;
- `expected`: exact outward-keyed `entry` and `behavior` slots in the public A schema;
- `lure_families`: one or more of `upstream_container`, `field_declaration`, `later_derivative`,
  `computed_value`, `sink_argument`, `wrong_context`, `nonexistent_present`, `nearby_statement`,
  `subexpression`, or `enclosing_function`;
- `forbidden_anchors`: zero or more existing structural lure anchors, each with `family`
  (`subexpression`, `field_declaration`, or `enclosing_function`), `kind` (`entry` or `behavior`),
  outward `revision`, and exact anchor. Statement-granularity cases require at least one;
- `changed_slot`: `entry` or `behavior` only for `changed_present_both`, otherwise null/omitted.

There are exactly two cases for each language × cell. Sources, effects, identifiers, and primary
syntax shapes are independent of development. No case contains v2 names/code, CWE/advisory ids,
commit metadata, or canonical vulnerable/fixed labels.

## Provider case schema

Each provider YAML file has schema `rd-v3-provider-heldout-case/v1` plus the same fields as one
public provider development case: `target`, `language`, `relation`, flat `files`, and four `edges`.
There are exactly two true and two false edges. The two frozen false families for that target each
appear once. Source and layout are independent of development.

## Mechanical acceptance

`rdv3_gate.py validate commitment.json` is the only materialization acceptance check. It verifies
hashes, Git cleanliness, counts, matrix, syntax, statement anchors, provider endpoint shapes,
near-miss families, treatment/construction bindings, and independence attestation. Failure is
`CALIBRATION_INVALID`; the curator does not issue a second batch.
