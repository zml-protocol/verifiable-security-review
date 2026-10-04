"""Spend accounting, the launch-budget guard and the stage-2 budget plan.

Everything here reads billing information only: the `total_cost_usd` of each
run's final `result` event in agent.jsonl. It never opens state.json,
transcripts or scores, so no budget decision can depend on results
(PREREGISTRATION.md §3.6).

    # after the preregistered gate slots have run:
    uv run python experiments/agent_verify/budget.py plan \
        --label claude_claude-sonnet-5_high --gate experiments/agent_verify/stage2_gate.txt \
        fixtures/authlib-jws-none/case.yaml fixtures/caddy-forward-auth/case.yaml \
        fixtures/filebrowser-archive-backslash/case.yaml
"""

from __future__ import annotations

import argparse
import json
import threading
from pathlib import Path

from validity import agent_events

from spike.models import CaseSpec

ROOT = Path(__file__).resolve().parents[2]
CONDITIONS = ("forward", "swapped", "identity_base", "identity_head")
TRIM_FIRST = "identity_base"  # the only condition the plan may drop (§3.6)


def run_cost(run_dir: Path, cap: float) -> float:
    """Billed cost of one attempt; an attempt that never reported one counts as the cap."""
    for event in reversed(agent_events(run_dir)):
        if event.get("type") == "result" and event.get("total_cost_usd") is not None:
            return float(event["total_cost_usd"])
    return cap


def attempts(protocol_root: Path, label: str) -> list[Path]:
    """Every started attempt for this model label, archived invalid attempts included.

    An attempt counts from the moment the runner opens its agent.jsonl, so one
    that dies before writing meta.json is still charged (at the cap).
    """
    return [log.parent for log in sorted(protocol_root.glob(f"*/*/*/{label}/r*/agent.jsonl"))]


def spent(protocol_root: Path, label: str, cap: float, exclude: set[Path] = frozenset()) -> float:
    return sum(run_cost(d, cap) for d in attempts(protocol_root, label) if d not in exclude)


class LaunchGuard:
    """Reserve `cap` for every in-flight run; refuse a launch that could cross the ceiling.

    This bounds launches, not billing: the CLI checks its own --max-budget-usd
    only between turns, so a running attempt can end above its reservation.
    """

    def __init__(self, protocol_root: Path, label: str, cap: float, ceiling: float):
        self.root, self.label, self.cap, self.ceiling = protocol_root, label, cap, ceiling
        self.in_flight: set[Path] = set()
        self._lock = threading.Lock()

    def reserve(self, run_dir: Path) -> tuple[bool, dict]:
        with self._lock:
            # In-flight attempts are covered by their reservation, not by their partial log.
            observed = spent(self.root, self.label, self.cap, exclude=self.in_flight)
            state = {"observed_spend": round(observed, 4), "in_flight": len(self.in_flight)}
            if observed + (len(self.in_flight) + 1) * self.cap > self.ceiling:
                return False, state
            self.in_flight.add(run_dir)
            return True, state

    def release(self, run_dir: Path) -> None:
        with self._lock:
            self.in_flight.discard(run_dir)


def read_gate(path: Path) -> list[str]:
    return [
        line.split("#", 1)[0].strip()
        for line in path.read_text().splitlines()
        if line.split("#", 1)[0].strip()
    ]


def design_slots(cases: list[CaseSpec], conditions: tuple[str, ...], repeats: int) -> list[str]:
    return [
        f"{c.id}/{h.id}/{cond}/r{k}"
        for c in cases
        for h in c.hypotheses
        for cond in conditions
        for k in range(repeats)
    ]


def plan(args: argparse.Namespace) -> None:
    root = ROOT / "runs" / "agent_verify" / args.protocol
    cases = [CaseSpec.load(p) for p in args.cases]
    gate = read_gate(args.gate)

    # A gate slot's calibration cost is every attempt it took, reruns included.
    gate_costs = {}
    for slot in gate:
        case, hyp, cond, rep = slot.split("/")
        cell = root / case / hyp / cond / args.label
        if not (cell / rep / "meta.json").exists():
            raise SystemExit(f"gate slot not attempted yet: {slot}")
        tries = [cell / rep, *sorted(cell.glob(f"{rep}.invalid*"))]
        gate_costs[slot] = round(sum(run_cost(d, args.cap) for d in tries), 4)

    per_run = max(gate_costs.values()) * (1 + args.buffer)
    observed = spent(root, args.label, args.cap)
    done = {
        "/".join(d.relative_to(root).parts[:3] + (d.name,))
        for d in attempts(root, args.label)
        if d.name.startswith("r") and d.name[1:].isdigit()
    }

    conditions, repeats = CONDITIONS, args.repeats
    steps = []

    def projection() -> float:
        remaining = [s for s in design_slots(cases, conditions, repeats) if s not in done]
        return observed + len(remaining) * per_run

    while projection() > args.ceiling:
        if TRIM_FIRST in conditions:
            conditions = tuple(c for c in conditions if c != TRIM_FIRST)
            steps.append(f"drop condition {TRIM_FIRST}")
        elif repeats > 0:
            repeats -= 1
            steps.append(f"repeats -> {repeats}")
        else:
            break

    full = design_slots(cases, CONDITIONS, args.repeats)
    kept = set(design_slots(cases, conditions, repeats)) | done
    result = {
        "protocol": args.protocol,
        "label": args.label,
        "ceiling_usd": args.ceiling,
        "gate_costs_usd": gate_costs,
        "per_run_estimate_usd": round(per_run, 4),
        "observed_spend_usd": round(observed, 4),
        "trim_steps": steps,
        "conditions": list(conditions),
        "repeats": repeats,
        "projected_total_usd": round(projection(), 2),
        "budget_censored": [s for s in full if s not in kept],
    }
    out = root / "budget_plan.json"
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "budget_censored"}, indent=2))
    print(f"budget-censored slots: {len(result['budget_censored'])}  (written to {out})")
    if repeats == 0:
        print("STOP: no further slots fit the launch budget; everything after the gate is censored")
        return
    print(
        "next: run.py <cases> --model <model> --effort <effort> --max-budget-usd "
        f"{args.cap} --total-budget-usd {args.ceiling} --conditions {' '.join(conditions)} "
        f"--repeats {repeats}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan", help="project the stage-2 design from the gate slots' billed cost")
    p.add_argument("cases", nargs="+", type=Path)
    p.add_argument("--label", required=True, help="run label, e.g. claude_claude-sonnet-5_high")
    p.add_argument("--gate", type=Path, required=True)
    p.add_argument("--protocol", default="v1.1")
    p.add_argument("--cap", type=float, default=3.0, help="preregistered per-run budget")
    p.add_argument("--ceiling", type=float, default=200.0)
    p.add_argument("--buffer", type=float, default=0.10)
    p.add_argument("--repeats", type=int, default=5)
    args = ap.parse_args()
    if args.command == "plan":
        plan(args)


if __name__ == "__main__":
    main()
