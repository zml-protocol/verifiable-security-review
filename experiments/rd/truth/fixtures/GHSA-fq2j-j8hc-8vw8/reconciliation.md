# SiYuan (GHSA-fq2j-j8hc-8vw8) — adjudication reconciliation & truth freeze

Three-way adjudication of the author requirement truth against two independent fresh judges
(§15.1). Judge A = gpt-6-astra (local Codex CLI, medium); Judge B = deepseek/deepseek-flash
(OpenCode `--standalone`); each fresh/isolated, tools off, one run, the verbatim-identical judge
bundle. Reconciliation is mechanical (`agreement.check`; opaque→real via `sheet-key.yaml`).

## Result (three-way unanimous)

| real item | kind | author | Judge A | Judge B | outcome |
|---|---|---|---|---|---|
| `entry-localpath` (item-07) | entry | REQUIRED | REQUIRED | REQUIRED | **admissible** |
| `behavior-sensitive-path-guard` (item-05) | behavior | REQUIRED | REQUIRED | REQUIRED | **admissible** |
| 6 distractors (item-01..04,06,08) | near-move / state-flip | NOT_REQUIRED | NOT_REQUIRED | NOT_REQUIRED | rejected by both |

`indeterminate=[]`, `distractor_conflicts=[]`, `two_sided_missing=[]`, `one_sided_missing=[]`,
`incomplete_truth_spec=false`, `qualifier_layer_inadmissible=false`.

Note: Judge A's pasted output dropped one character at `missing: [`; the operator confirmed the
intended value was `missing: []` (format-only; labels unchanged and identical to Judge B). No
two-sided (or one-sided) missing requirement.

## Verdict — SiYuan fixture truth FROZEN

- entry and behavior are three-way admissible → the fixture is admissible (no §15.2 reserve
  substitution).
- Frozen scored truth: `entry = localPath := n.TokensStr()` (present both revisions);
  `behavior = the added IsSensitivePath guard` (fixed present / vuln absent, context = the copy
  site it gates).
- Route hardening (CheckAdminRole/CheckReadonly) and the `/etc` dedup remain non-scored notes, not
  requirements.
- `requirement-truth.yaml`, `executable-truth.md`, the judge bundle, both judge outputs, and the
  sheet key are the frozen record. The evaluated RD agent never sees any of this.

Next in the frozen queue: Vikunja (Go #2).
