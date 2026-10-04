# Adjudication instructions — RD requirement truth (§15.1)

You are one of two independent truth adjudicators for one security-fix fixture. Decide, for the
stated claim, which requirement items are genuinely required to establish it.

**Use only this bundle:** `definitions.yaml` (the frozen operational definitions), the code context
at the `vuln` and `fixed` revisions (`code-context/`), `fix-diff.patch`, `advisory-evidence.md`, and
`execution-evidence.md`. Do not use any other source.

**Claim:** in a JWT-configured Mnemosyne sync server, an unauthenticated network client-controlled
Authorization header containing a well-formed, unexpired HS256 bearer JWT with a forged signature
may bypass authentication (CWE-347) and gain read or modification access to sync data. **Domain:**
the sync endpoint is network-reachable and has a JWT secret configured. The attacker controls the
HTTP Authorization header, including the bearer token's header, payload, and signature, but does
not know the configured secret and has no valid credential. The triggering token declares HS256,
has a future expiration, is otherwise well-formed, and has an invalid signature. Every other state
(sync data, accounts, environment, and server configuration) may take any value the code allows.

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
