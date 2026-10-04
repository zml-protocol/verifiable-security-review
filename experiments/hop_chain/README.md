# Chain replication (PREREGISTRATION.md §12)

    uv run python fixtures/_objdev/build.py && uv run python fixtures/_objcal/build.py
    uv run python experiments/hop_chain/connector.py calibrate --set dev   # development only
    uv run python experiments/hop_chain/connector.py calibrate --set cal   # once, after the freeze
    uv run python experiments/hop_chain/connector.py freeze --targets eval # after the freeze
    uv run python experiments/hop_chain/replicate.py run --order experiments/hop_chain/order.txt \
        --model claude-sonnet-5 --effort high
    uv run python experiments/hop_chain/replicate_score.py --out results/chain-replication.json

- `queries/go/SameObject.ql`, `connector.py`: the same-object connector (SAME_OBJECT /
  NOT_PROVEN_SAME from explicit SSA definitions); `connector/{dev,cal}.yaml` its pairs.
- `chain.py`: edges, connectors, simple paths, qualifier, the five chain classes.
- `anchors.yaml`: rule-G entry/terminal per fixture and revision (scoring only).
- `replicate.py` / `replicate_score.py`: one-shot sessions identical to the P-Hybrid-2 initial
  phase, scored descriptively with Wilson intervals.
- `diagnose.py`: the §12.0 design diagnostic (committed before it ran; design information only).
