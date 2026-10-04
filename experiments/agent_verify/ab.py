"""v2 path-citation A/B: preregistered run order and the arm comparison.

    # 1. write the matched, blocked run order (committed before any v2 run)
    uv run python experiments/agent_verify/ab.py order --seed 20260927 \
        --out experiments/agent_verify/v2_order.txt <cases...>

    # 2. after scoring each arm separately with score.py --label ... --out ...
    uv run python experiments/agent_verify/ab.py compare \
        --control results/v2-control.json --treatment results/v2-treatment.json

Blocks are hypothesis x condition x repeat; each block holds one control and
one treatment run whose order is drawn from the seed. Blocks are laid out
repeat-major, so every repeat wave covers every hypothesis before the next.
Definitions: PREREGISTRATION.md §8.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean

from run import read_order

from spike.models import CaseSpec

CONDITIONS = ("forward", "swapped")
ARMS = ("control", "treatment")
PATH_FACT_MARKERS = ("reaches", "run-on-2xx", "becomes-entry")

# The metric part of success needs all three (§8.4).
MIN_TREATMENT_EVIDENCE = 0.60
MIN_EVIDENCE_GAIN = 0.20
MIN_TREATMENT_ATTRIBUTION = 0.80
MAX_ATTRIBUTION_DROP = 0.10
# A hypothesis x condition cell needs this many complete VALID pairs out of 5 (§8.2).
MIN_PAIRS_PER_CELL = 4
MAX_INFRA_INVALID_RATE = 0.05
ZERO_INVARIANTS = (
    "anchor_audit_failures", "accepted_revision_mismatches", "harness_errors",
    "runs_with_foreign_tools", "runs_with_context_leak",
)  # fmt: skip


def harness_ok(summary: dict) -> tuple[bool, dict]:
    inv = summary["harness_invariants"]
    failing = {k: inv[k] for k in ZERO_INVARIANTS if inv[k] != 0}
    if inv["infra_invalid_rate"] > MAX_INFRA_INVALID_RATE:
        failing["infra_invalid_rate"] = inv["infra_invalid_rate"]
    return not failing, failing


def order(args: argparse.Namespace) -> None:
    rng = random.Random(args.seed)
    cases = [CaseSpec.load(p) for p in args.cases]
    lines = [f"# v2 order: seed {args.seed}; blocks = hypothesis x condition x repeat"]
    block = 0
    for k in range(args.repeats):
        for case in cases:
            for h in case.hypotheses:
                for cond in CONDITIONS:
                    block += 1
                    arms = list(ARMS)
                    if rng.random() < 0.5:
                        arms.reverse()
                    for arm in arms:
                        lines.append(f"{arm} {case.id}/{h.id}/{cond}/r{k}  # block {block}")
    args.out.write_text("\n".join(lines) + "\n")
    print(f"{block} blocks, {2 * block} runs -> {args.out}")


def _slot(run: dict) -> str:
    # run["run"] = <case>/<hyp>/<condition>/<label>/r<k>
    case, hyp, cond, _label, rep = run["run"].split("/")
    return f"{case}/{hyp}/{cond}/{rep}"


def _is_path(fact_id: str) -> bool:
    return any(m in fact_id for m in PATH_FACT_MARKERS)


def _mean(values: list) -> float | None:
    return mean(values) if values else None


def _rates(runs: list[dict]) -> dict:
    path = [ok for r in runs for f, ok in r["facts_covered"].items() if _is_path(f)]
    flip = [ok for r in runs for f, ok in r["facts_covered"].items() if not _is_path(f)]
    return {
        "n": len(runs),
        "evidence_complete_correct": _mean([r["evidence_complete_correct"] for r in runs]),
        "attribution_correct": _mean([r["attribution_correct"] for r in runs]),
        "path_fact_citation": _mean(path),
        "flip_fact_citation": _mean(flip),
    }


def compare(args: argparse.Namespace) -> None:
    arms = {
        "control": json.loads(args.control.read_text()),
        "treatment": json.loads(args.treatment.read_text()),
    }
    valid = {
        arm: {_slot(r): r for r in data["runs"] if r["validity"] == "VALID"}
        for arm, data in arms.items()
    }
    # The design is the preregistered order, not whatever happened to run: a pair counts
    # only if both of its runs are VALID; censored, invalid or missing pairs drop out.
    designed = {slot for _, slot in read_order(args.order)}
    paired = sorted(designed & set(valid["control"]) & set(valid["treatment"]))
    dropped = sorted(designed - set(paired))
    runs = {arm: [valid[arm][s] for s in paired] for arm in ARMS}

    overall = {arm: _rates(runs[arm]) for arm in ARMS}
    by_case: dict[str, dict] = defaultdict(dict)
    by_hyp: dict[str, dict] = defaultdict(dict)
    for arm in ARMS:
        groups_case, groups_hyp = defaultdict(list), defaultdict(list)
        for r in runs[arm]:
            groups_case[r["case"]].append(r)
            groups_hyp[f"{r['case']}/{r['hypothesis']}"].append(r)
        for key, group in groups_case.items():
            by_case[key][arm] = _rates(group)
        for key, group in groups_hyp.items():
            by_hyp[key][arm] = round(mean(g["evidence_complete_correct"] for g in group), 3)

    pairs_per_cell: dict[str, int] = defaultdict(int)
    for slot in paired:
        pairs_per_cell[slot.rsplit("/", 1)[0]] += 1
    expected_cells = {slot.rsplit("/", 1)[0] for slot in designed}
    thin = {cell: pairs_per_cell.get(cell, 0) for cell in sorted(expected_cells)
            if pairs_per_cell.get(cell, 0) < MIN_PAIRS_PER_CELL}
    harness = {arm: harness_ok(data) for arm, data in arms.items()}

    t, c = overall["treatment"], overall["control"]
    # The statistical criteria only exist when the design is adequately filled (§8.2).
    criteria: dict[str, bool] = {}
    gain = None
    if not thin:
        gain = t["evidence_complete_correct"] - c["evidence_complete_correct"]
        criteria = {
            "treatment_evidence_complete>=0.60": t["evidence_complete_correct"]
            >= MIN_TREATMENT_EVIDENCE,
            "gain>=0.20": gain >= MIN_EVIDENCE_GAIN,
            "treatment_attribution>=0.80_and_drop<=0.10": (
                t["attribution_correct"] >= MIN_TREATMENT_ATTRIBUTION
                and c["attribution_correct"] - t["attribution_correct"] <= MAX_ATTRIBUTION_DROP
            ),
        }
    metric_success = bool(criteria) and all(criteria.values())
    harness_clean = all(ok for ok, _ in harness.values())
    if thin:
        verdict = "INCONCLUSIVE_INFRA"
    elif not harness_clean:
        verdict = "HARNESS_INVALID"
    else:
        verdict = "SUCCESS" if metric_success else "FAIL"
    result = {
        "verdict": verdict,
        "experiment_success": verdict == "SUCCESS",
        "metric_success": metric_success,
        "criteria": criteria,
        "harness": {arm: {"ok": ok, "failing": failing} for arm, (ok, failing) in harness.items()},
        "pairs": len(paired),
        "pairs_per_cell": dict(sorted(pairs_per_cell.items())),
        "cells_below_minimum": thin,
        "dropped_pairs": dropped,
        "overall": overall,
        "gain_evidence_complete": None if gain is None else round(gain, 3),
        "by_fixture": by_case,  # Caddy is reported on its own (§8.5)
        "evidence_complete_by_hypothesis": by_hyp,
    }
    if args.out:
        args.out.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "dropped_pairs"}, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    o = sub.add_parser("order")
    o.add_argument("cases", nargs="+", type=Path)
    o.add_argument("--seed", type=int, required=True)
    o.add_argument("--repeats", type=int, default=5)
    o.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("compare")
    c.add_argument("--control", type=Path, required=True)
    c.add_argument("--treatment", type=Path, required=True)
    c.add_argument("--out", type=Path)
    c.add_argument("--order", type=Path, default=Path(__file__).parent / "v2_order.txt",
                   help="the preregistered design the pairs are checked against")
    args = ap.parse_args()
    {"order": order, "compare": compare}[args.command](args)


if __name__ == "__main__":
    main()
