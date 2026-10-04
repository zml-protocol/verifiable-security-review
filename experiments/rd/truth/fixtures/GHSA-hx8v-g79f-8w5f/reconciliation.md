# LiteLLM (GHSA-hx8v-g79f-8w5f) — adjudication reconciliation & truth freeze

Three-way adjudication under frozen §15.1. Judge A = `gpt-6.1-sol` (Codex CLI, medium); Judge B =
`deepseek/deepseek-flash` (OpenCode `--standalone`); each successful run used a fresh isolated
session, tools off, an empty working directory, and the byte-identical frozen `judge-prompt.md`.
Mechanical reconciliation used `agreement.check` after opaque ids were mapped through
`sheet-key.yaml`.

## Result — three-way unanimous

| real item | opaque id | kind | author | Judge A | Judge B | outcome |
|---|---|---|---|---|---|---|
| `entry-user-config-extraction` | `item-03` | entry | REQUIRED | REQUIRED | REQUIRED | **admissible** |
| `behavior-user-config-ban` | `item-04` | behavior | REQUIRED | REQUIRED | REQUIRED | **admissible** |
| 6 distractors | other items | near-move / state-flip | NOT_REQUIRED | NOT_REQUIRED | NOT_REQUIRED | all rejected |

Frozen `agreement.check` result:

- `admissible = [behavior-user-config-ban, entry-user-config-extraction]`
- `indeterminate = []`
- `distractor_conflicts = []`; all six distractors rejected
- `missing_labels = []`; `two_sided_missing = []`; `one_sided_missing = []`
- `ambiguity_burden = 0`; `incomplete_truth_spec = false`
- `vocabulary_blind_spots = []`; `qualifier_layer_inadmissible = false`

Judge B wrapped its YAML in a Markdown fence; the trailing fence was removed from `judge-b.yaml` as
a format-only normalization. The raw transcript is preserved unchanged.

## Verdict — fixture truth FROZEN

- Entry: EN-2 extraction of the attacker-controlled request field at
  `router_config = data.pop("user_config")`, present in both revisions.
- Behavior: BE-1 changed request-body check at the `banned_params` assignment, present in both
  revisions; the fixed realization adds `user_config` and therefore causes the immediately following
  membership guard to reject the triggering body.
- No scored qualifier. Authentication is part of the scenario; unrelated same-commit hardening is
  recorded only in `non_scored_notes`.
- Entry and behavior are both three-way admissible, so LiteLLM is Python frozen fixture #1 and no
  §15.2 reserve substitution is triggered.

## Infrastructure note

The first sandboxed invocation of `run_judges.sh` failed before producing any model labels: Judge A
could not reach its service, and Judge B failed before reading the prompt because the relative
fixture path became invalid in its empty working directory and its normal log path was read-only.
The successful invocation used the fixture's absolute path and one-time permission for network and
normal CLI logging. It launched new isolated sessions with the same frozen prompt; no author artifact
changed between attempts.
