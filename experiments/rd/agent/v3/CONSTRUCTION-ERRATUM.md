# RD v3 construction erratum 1

Status: **construction freeze v1 is invalid; superseded only by a separately committed v2
manifest.** No treatment implementation, held-out materialization, fresh selection, model call, or
measurement occurred under v1.

## Defect

Construction freeze v1 (`construction-freeze.json`, created from `353778d`) correctly mapped the
eligible Python provider target to the already-frozen `call_typed_attribute` relation, whose source
endpoint is a nested attribute call of the form `a.b.m(...)`. Its public development instance in
`provider-development.yaml`, however, used `checker.inspect(...)`, whose receiver is a simple name.
That call is a method call but is not the relation's frozen `attribute_method_call` endpoint kind.
The v1 validator checked syntax and endpoint text but did not check this relation-specific source
shape, so it accepted a non-conforming construction input.

This was detected during the first read-only implementation audit, before any provider query,
prompt, harness treatment, held-out instance, or model output existed. It is therefore a
construction-conformance correction, not adaptation to an observed treatment result.

## Bounded correction

- Preserve every v1 file and `construction-freeze.json` byte-for-byte for audit.
- Replace the complete provider development corpus, for treatment purposes only, with
  `provider-development-v2.yaml`. Its Python calls use the required `a.b.m(...)` shape; its Go
  cases and all frozen true/false counts and families are unchanged.
- Use `construction_freeze_v2.py`, which first verifies the immutable v1 freeze, then validates the
  replacement corpus and explicitly checks the nested Python call shape.
- Bind this erratum, the replacement corpus, the v2 validator, the v1 manifest, and every original
  bound input in `construction-freeze-v2.json`.

No cell count, relation truth, endpoint role, provider target, false family, gate, budget, sample,
model, or terminal rule changes. Any further construction defect invalidates v2 and requires a new
review; it may not be silently patched.
