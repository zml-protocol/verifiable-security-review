# Anchor self-review — GHSA-hx8v-g79f-8w5f (author-side)

Completed before `build_sheet` and before either judge saw the fixture, against the frozen
`ANCHOR-SELF-REVIEW.md` and `definitions.yaml`.

## Entry: `entry-user-config-extraction`

- [x] EN-2 applies: the claim names `user_config`, one field of the larger request-body object.
- [x] The anchor is the single assignment that first extracts that field into its own value:
  `router_config = data.pop("user_config")`.
- [x] It is not the later derived `filtered_config`, Router construction, or outbound call.
- [x] It is statement-granular, not a whole function and not the sub-expression `data.pop(...)`.
- [x] Repository search found no earlier product-code extraction of the request field; the earlier
  `"user_config" in data` is a membership test, not a definition that extracts the value.

## Behavior: `behavior-user-config-ban`

- [x] BE-1 applies: the fix changes the request-body guard by adding `user_config` to the list used
  by the immediately following membership check.
- [x] The changed assignment is the only changed check/transform for this SSRF claim; BE-3 does not
  produce competing branches.
- [x] It directly decides whether the guard iterates over and rejects `user_config` for the triggering
  body. The later routing statements implement the admitted effect but are not the changed check.
- [x] Both revision realizations are statement-granular `Assign` nodes.

## Absent context and qualifiers

- [x] Neither item has an absent revision, so AC-1/AC-2/AC-3 do not apply.
- [x] No claim-necessary qualifier is forced into the closed vocabulary. Authentication is stated in
  the scenario, and the other same-commit hardening changes are not necessary for this SSRF claim.

## Matcher sanity

- [x] All four anchors resolve uniquely with the frozen resolver under Python 3.13.
- [x] Entry resolves to `Assign` at structural path `(5, 2)` in both revisions, with identical digest
  `9119a308...`.
- [x] Behavior resolves to `Assign` at structural path `(17, 3)` in both revisions; its digest changes
  from `835628ec...` (vuln) to `0ac0dfc4...` (fixed), as intended.
- [x] Per-revision line numbers were checked against both trees.

Author truth is ready for bundle construction. After a judge sees the bundle, it is immutable except
for the charter's two-sided-missing-item path.
