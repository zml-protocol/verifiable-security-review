# Vikunja (GHSA-mr3j-p26x-72x4) — adjudication reconciliation & truth freeze

Three-way adjudication (§15.1). Judge A = gpt-6-astra (Codex CLI, medium); Judge B =
deepseek/deepseek-flash (OpenCode `--standalone`); each fresh/isolated, tools off, one run, the
verbatim-identical bundle. Mechanical reconciliation (`agreement.check`; opaque→real via sheet-key).

## Result (three-way unanimous)

| real item | kind | author | Judge A | Judge B | outcome |
|---|---|---|---|---|---|
| `entry-readone-request` (item-04) | entry | REQUIRED | REQUIRED | REQUIRED | **admissible** |
| `behavior-task-scope-constraint` (item-07) | behavior | REQUIRED | REQUIRED | REQUIRED | **admissible** |
| 6 distractors | near-move / state-flip | NOT_REQUIRED | NOT_REQUIRED | NOT_REQUIRED | all rejected |

`indeterminate=[]`, `distractor_conflicts=[]`, `two_sided_missing=[]`, `one_sided_missing=[]`,
`incomplete_truth_spec=false`, `qualifier_layer_inadmissible=false`. (Judge A's paste used
markdown-escaped underscores / `\[\]`; de-escaped, content unchanged.)

## Verdict — Vikunja fixture truth FROZEN

- entry and behavior three-way admissible → fixture admissible (no §15.2 reserve substitution).
- Frozen scored truth: `entry = TaskComment.ReadOne request-bound receiver` (present both revisions);
  `behavior = the added .And("task_id = ?", tc.TaskID) task-scope constraint` (fixed present / vuln
  absent, context = the diff-aligned `NoAutoCondition().`).
- Single-line fix; no qualifier. Frozen record under the fixture dir; the evaluated RD agent never
  sees it.

Next in the frozen queue: DHCP (Go #3).
