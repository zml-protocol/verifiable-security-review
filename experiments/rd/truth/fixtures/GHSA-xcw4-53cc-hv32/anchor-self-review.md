# Anchor self-review — GHSA-xcw4-53cc-hv32 (author-side)

Completed before `build_sheet` and before either judge saw the fixture, against the frozen
`ANCHOR-SELF-REVIEW.md` and `definitions.yaml`.

## Entry: `entry-authorization-header`

- [x] EN-2 applies: the claim names the Authorization header, one field of the larger HTTP request.
- [x] The anchor is the assignment that first extracts that field from `self.headers` on the JWT
  path: `auth = self.headers.get("Authorization", "")`.
- [x] It is earlier than bearer-prefix checking, token slicing, JWT decoding, or validation; those
  are derived uses rather than the entry.
- [x] It is statement-granular (`Assign`), not the whole `_check_auth` method and not the
  `self.headers.get(...)` sub-expression.
- [x] The earlier identical extraction at line 91/145 is on the mutually exclusive API-key branch;
  with `jwt_secret` configured and `api_key` absent in the stated domain, execution reaches the
  line 100/154 extraction instead.

## Behavior: `behavior-invalid-signature-guard`

- [x] BE-1 applies: the fix adds `if not valid_signature:`, the guard that rejects a failed
  HMAC-SHA256 comparison.
- [x] BE-3 remains determinate for the triggering input. Its JWT has three well-formed segments, a
  dictionary header/payload, `alg: HS256`, and a future `exp`, so the format, type, algorithm, and
  expiry checks do not decide this execution. The invalid-signature guard is the changed check that
  directly rejects it before authentication succeeds.
- [x] The anchor is the statement-level `If`, not the sub-expression `not valid_signature`, the
  preceding comparison assignment, the raised exception, or the whole `_validate_jwt` method.
- [x] The vulnerable revision has no signature check. Under AC-1, its absent context is the
  counterpart of the first statement after the new guard: `exp = payload.get("exp", 0)`.
- [x] The fixed statement after the guard is `exp = payload.get("exp")`; the vulnerable context is
  the corresponding pre-fix expiration assignment, not a sub-expression or the later `return True`.

## Qualifiers

- [x] No claim-necessary qualifier is forced into the closed vocabulary. JWT-secret configuration
  and endpoint reachability are fixed by the stated scenario rather than varying requirements.
- [x] Algorithm, encoding/type, and expiration changes do not decide the stated triggering input and
  are recorded as non-scored same-commit hardening rather than forced qualifiers.

## Matcher sanity

- [x] All four anchors/contexts resolve uniquely with the frozen resolver under Python 3.13.
- [x] Entry resolves to `Assign` at structural paths `(12, 9, 5, 1)` (vuln) and `(15, 11, 5, 1)`
  (fixed), with identical digest `80221cbe...`.
- [x] Fixed behavior resolves to `If` at path `(15, 10, 14)`, digest `13b419e0...`.
- [x] Vulnerable absent context resolves to `Assign` at path `(12, 9, 5, 4, 8)`, digest
  `2aa96766...`.
- [x] Per-revision line numbers were checked against both trees.

Author truth is ready for bundle construction. After a judge sees the bundle, it is immutable except
for the charter's two-sided missing-item path.
