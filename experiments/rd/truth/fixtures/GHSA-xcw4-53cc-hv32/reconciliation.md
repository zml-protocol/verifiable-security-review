# Mnemosyne (GHSA-xcw4-53cc-hv32) — adjudication reconciliation & truth freeze

Three-way adjudication under frozen §15.1. Judge A = `gpt-6.1-sol` (Codex CLI, medium); Judge B =
`deepseek/deepseek-flash` (OpenCode `--standalone`); each successful run used a fresh isolated
session, tools off, an empty working directory, and the byte-identical frozen `judge-prompt.md`.
Mechanical reconciliation used `agreement.check` after opaque ids were mapped through
`sheet-key.yaml`.

## Result — three-way unanimous

| real item | opaque id | kind | author | Judge A | Judge B | outcome |
|---|---|---|---|---|---|---|
| `entry-authorization-header` | `item-03` | entry | REQUIRED | REQUIRED | REQUIRED | **admissible** |
| `behavior-invalid-signature-guard` | `item-01` | behavior | REQUIRED | REQUIRED | REQUIRED | **admissible** |
| 6 distractors | other items | near-move / state-flip | NOT_REQUIRED | NOT_REQUIRED | NOT_REQUIRED | all rejected |

Frozen `agreement.check` result:

- `admissible = [behavior-invalid-signature-guard, entry-authorization-header]`
- `indeterminate = []`
- `distractor_conflicts = []`; all six distractors rejected
- `missing_labels = []`; `two_sided_missing = []`; `one_sided_missing = []`
- `ambiguity_burden = 0`; `incomplete_truth_spec = false`
- `vocabulary_blind_spots = []`; `qualifier_layer_inadmissible = false`

Judge B wrapped its YAML in a Markdown fence; the trailing fence was removed from `judge-b.yaml` as
a format-only normalization. The raw transcript is preserved unchanged.

## Verdict — fixture truth FROZEN

- Entry: EN-2 extraction of the attacker-controlled Authorization header at
  `auth = self.headers.get("Authorization", "")` on the JWT branch, present in both revisions.
- Behavior: BE-1/BE-3 added `if not valid_signature:` guard, fixed present / vulnerable absent;
  AC-1 vulnerable context is the corresponding expiration assignment immediately after where the
  guard would protect later acceptance.
- The triggering input is deliberately narrow: well-formed, `alg: HS256`, future expiry, invalid
  signature. Thus format, type, algorithm, and expiry hardening do not compete for behavior; they
  remain non-scored same-commit notes.
- JWT-secret configuration and endpoint reachability are fixed by the scenario, not scored
  qualifiers.
- Entry and behavior are both three-way admissible, so Mnemosyne substitutes for Reflex and becomes
  Python frozen fixture #2. No further §15.2 reserve substitution is triggered.
