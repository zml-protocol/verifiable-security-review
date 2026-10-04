# P-Hybrid-2: typed-hop proposals and one-shot verifier feedback (PREREGISTRATION.md §11)

    uv run python experiments/hop_propose/freeze_rows.py          # frozen verifier output (once, at freeze)
    uv run python experiments/hop_propose/propose_run.py run --pilot --model claude-haiku-4-5-20251001 --budget-usd 1
    uv run python experiments/hop_propose/propose_run.py run --order experiments/hop_propose/order.txt \
        --model claude-sonnet-5 --effort high
    uv run python experiments/hop_propose/propose_score.py --out results/p-hybrid-2-scores.json
    uv run python experiments/hop_propose/propose_review.py export   # blind review sheet

- A block is one (fixture, repeat): a parent session locks the initial hops, its state is
  snapshotted, and control and treatment fork the parent (`--resume --fork-session`) at the
  same time for one revision. Only the treatment message carries the verdict block.
- The agent side lives in `src/spike/hop_session.py` / `hop_mcp_server.py`; the shared hop
  core (anchors, node kinds, identities, frozen verdicts) in `src/spike/hops.py`.
- `frozen/`: every relation verifier's rows and the shape rows per revision, with a sha256
  manifest; nothing runs CodeQL during P-Hybrid-2.
- `vocabulary.yaml`: the relation and node-kind text the agent sees (identical in both arms).
- Runs go to `runs/hop_propose/<protocol>/<fixture>/r<k>/{initial,control,treatment}`.
