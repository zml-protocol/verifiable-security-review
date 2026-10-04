# Completeness Repair (PREREGISTRATION.md §13)

    uv run python experiments/hop_repair/power.py                    # the discrete effect-size table
    uv run python experiments/hop_repair/repair_run.py run --model claude-sonnet-5 --effort high
    uv run python experiments/hop_repair/repair_score.py --out results/completeness-repair.json

- `contract.yaml`: the semantic task contract (generic rules + the frozen golden path-fact
  statement of each fixture, verbatim), shown to both arms in every phase.
- `messages.py`: control = the P-Hybrid-2 revision message; treatment = control + one sentence.
- `repair_run.py`: opportunity sampling; one initial session per visit, classified with the
  frozen §12 classifier; only incomplete initials fork (P-Hybrid-2 fork plumbing).
- `repair_score.py`: T_only / C_only / Both / Neither per fixture, sign test + per-fixture
  direction, verdict order PROTOCOL_INVALID -> HARNESS_INVALID -> INCONCLUSIVE_OPPORTUNITY ->
  SUCCESS / FAIL.
