"""Chain replication runner (PREREGISTRATION.md §12.2). No feedback, no fork: each block is one
session, byte-identical in interface to the P-Hybrid-2 initial phase (prompt, get_task,
vocabulary, validate_hop, submit_hops, one lock).

    uv run python experiments/hop_chain/replicate.py order --out experiments/hop_chain/order.txt
    uv run python experiments/hop_chain/replicate.py run --order experiments/hop_chain/order.txt \
        --model claude-sonnet-5 --effort high
    uv run python experiments/hop_chain/replicate.py run --pilot --model claude-haiku-4-5-20251001 --budget-usd 1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "hop_propose"))

import propose_run as P

sys.path.insert(0, str(HERE))
import connector as C

PROTOCOL = "c1"
SEED = 20261001
REPEATS = 10


def runs_root(pilot: bool) -> Path:
    return ROOT / "runs" / "hop_chain" / (f"{PROTOCOL}-pilot" if pilot else PROTOCOL)


def run_one(fixture: str, repeat: int, args: argparse.Namespace) -> str:
    run_dir = runs_root(args.pilot) / fixture / f"r{repeat}"
    attempt = 1
    if (run_dir / "meta.json").exists():
        validity, reason = P.classify(run_dir)
        if validity != P.INFRA_INVALID:
            return f"{validity}:{reason}"
        if json.loads((run_dir / "meta.json").read_text()).get("attempt", 1) >= P.MAX_ATTEMPTS:
            return f"{P.INFRA_INVALID}:{reason}:exhausted"
        attempt = P.archive(run_dir)
    config = P.session_config(fixture, args.pilot, repeat, run_dir, "initial", None)
    config.session_id = f"{PROTOCOL}/{fixture}/r{repeat}"
    mcp = P.write_config(config, run_dir)
    workdir = P.isolated_workdir()
    session_id = str(uuid.uuid4())
    cmd = P.claude_cmd(P.PROMPT, mcp, args, session_id=session_id, resume=None)
    code, seconds = P.execute(cmd, workdir, run_dir, args.timeout)
    meta = {"protocol": PROTOCOL, "harness": args.harness, "fixture": fixture, "repeat": repeat,
            "attempt": attempt, "model": args.model, "effort": args.effort,
            "max_budget_usd": args.budget_usd, "timeout": args.timeout, "exit": code,
            "seconds": seconds, "session_id": session_id,
            "served_session": P.served_session(run_dir), "cost_usd": P.cost_of(run_dir),
            "prompt_sha256": hashlib.sha256(P.PROMPT.encode()).hexdigest(),
            "agent_environment": P.agent_environment(run_dir),
            "cmd": ["claude", "-p", "<prompt elided>", *cmd[3:]]}
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    session_file = P.agent_session_file(session_id)
    if session_file:
        shutil.copyfile(session_file, run_dir / "cli-session.jsonl")
        memory = session_file.parent / "memory"
        if not (memory.is_dir() and any(memory.iterdir())):
            shutil.rmtree(session_file.parent, ignore_errors=True)
    shutil.rmtree(workdir, ignore_errors=True)
    validity, reason = P.classify(run_dir)
    return f"{validity}:{reason}"


def order(args: argparse.Namespace) -> None:
    fixtures = sorted(P.CASES["eval"])
    rng = random.Random(SEED)
    lines = []
    for r in range(REPEATS):
        rnd = [(f, r) for f in fixtures]
        rng.shuffle(rnd)
        lines += [f"{f} r{k}\n" for f, k in rnd]
    args.out.write_text("".join(lines))
    print(f"{args.out}: {len(lines)} blocks")


def formal_preconditions() -> list[str]:
    """§12.1: the connector passed its held-out calibration and its rows exist for every
    evaluation revision. Otherwise nothing runs (there is no fallback connector)."""
    return C.gate() + C.rows_problems("eval")


def run(args: argparse.Namespace) -> None:
    commit, dirty = P.harness_commit()
    if dirty and not (args.pilot or args.allow_dirty):
        sys.exit("working tree is dirty; evaluation runs start from the frozen commit only")
    if not args.pilot and (problems := formal_preconditions()):
        sys.exit("no evaluation session starts: " + "; ".join(problems))
    args.harness = {"commit": commit, "dirty": dirty}
    blocks = [(f, 0) for f in sorted(P.CASES["pilot"])] if args.pilot else P.read_order(args.order)
    for fixture, repeat in blocks:
        status = run_one(fixture, repeat, args)
        print(f"{status:28} {fixture}/r{repeat}", flush=True)
        if "usage_limit" in status:
            print("STOP: usage limit reached; rerun the remaining blocks later", flush=True)
            return


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("order")
    o.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("run")
    r.add_argument("--order", type=Path)
    r.add_argument("--pilot", action="store_true")
    r.add_argument("--model", required=True)
    r.add_argument("--effort", default=None)
    r.add_argument("--budget-usd", type=float, default=3.0)
    r.add_argument("--timeout", type=int, default=1200)
    r.add_argument("--allow-dirty", action="store_true", help="never for the evaluation run")
    args = ap.parse_args()
    if args.cmd == "run" and not (args.pilot or args.order):
        ap.error("run needs --order or --pilot")
    {"order": order, "run": run}[args.cmd](args)


if __name__ == "__main__":
    main()
