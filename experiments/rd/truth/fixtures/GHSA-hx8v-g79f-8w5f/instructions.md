# Adjudication instructions — RD requirement truth (§15.1)

You are one of two independent truth adjudicators for one security-fix fixture. Decide, for the
stated claim, which requirement items are genuinely required to establish it.

**Use only this bundle:** `definitions.yaml` (the frozen operational definitions), the code context
at the `vuln` and `fixed` revisions (`code-context/`), `fix-diff.patch`, `advisory-evidence.md`, and
`execution-evidence.md`. Do not use any other source.

**Claim:** in LiteLLM Proxy, an authenticated caller-controlled `user_config` request field
containing a nested `api_base` may lead to CWE-918 Server-Side Request Forgery by steering the
proxy's outbound request to a host chosen by the caller. **Domain:** the attacker has a valid
virtual key and controls the proxy request body, including `user_config` and its nested `api_base`.
Every other state (proxy configuration, models, credentials, environment, network, and destination
services) may take any value the code allows.

**Task — for every item in `adjudication-sheet.yaml`:**
- Judge it **independently** against the operational definitions. Label it `REQUIRED`,
  `NOT_REQUIRED`, or `INDETERMINATE`.
- `REQUIRED` means: for the claim to hold, this exact requirement (its kind, its per-revision
  present/absent state, and its anchored program points) must be true. Do **not** label an item
  `REQUIRED` merely because the fix touches that code — necessity is judged from the definitions and
  the claim, not from "the commit changed it".
- `INDETERMINATE` means the definitions do not decide it on the evidence given.

**Missing items (optional):** if you believe a required requirement is absent from the sheet, list
it in the frozen requirement schema (kind + per-revision anchors). Each anchor must resolve to a real
program point shown in the supplied code context.

Give one label for every item id. Your final output must use the exact YAML schema at the end of the
inlined prompt and contain no prose outside that YAML.
