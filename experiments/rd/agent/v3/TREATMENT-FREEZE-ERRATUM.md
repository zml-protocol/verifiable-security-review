# RD v3 treatment-freeze erratum

The freeze committed at `f9c20e5` (`treatment-freeze.json`, schema v1) is **PRE-GATE
INCOMPLETE**. It bound the treatment runtime, formal scorer, provider, and offline pilot, but omitted
the held-out commitment validator, deterministic provider-gate runner, and A-gate scorer. Running
the held-out tranche under that freeze would therefore leave the frozen gate rules without a bound
mechanical implementation.

This was found during the final pre-authorization audit. At discovery time:

- no held-out A or provider instance had been created, materialized, inspected, or unsealed;
- no v3 paid model call had occurred;
- no held-out outcome existed;
- the public development result and treatment behavior were unchanged.

The correction adds only measurement plumbing already required by `CONSTRUCTION-SPEC.md` and
`V3-PROTOCOL-DELTA.md`: a committed-batch validator, deterministic A preparation/scoring, the
one-shot provider evaluation with one infrastructure-only retry, and combined gate disposition.
It changes no prompt, schema-calibration example, provider query, relation semantics, threshold,
case count, or intervention. `treatment-freeze-v2.json` supersedes the incomplete v1 freeze; v1 is
retained unchanged as provenance.
