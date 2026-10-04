"""§13 Completeness Repair runner (PREREGISTRATION.md §13).

    uv run python experiments/hop_repair/repair_run.py run --model claude-sonnet-5 --effort high
    uv run python experiments/hop_repair/repair_run.py run --pilot --force-fork \
        --model claude-haiku-4-5-20251001 --budget-usd 1

Opportunity sampling: fixtures are visited round-robin in a seeded order per round. Each
visit runs one initial session (the P-Hybrid-2 initial phase plus the §13 contract), locks
it, and classifies it with the frozen §12 classifier. Only an initially incomplete block is
forked (P-Hybrid-2 fork plumbing): control gets the P-Hybrid-2 revision message, treatment
the same plus one sentence. A fixture stops at its target (repair_score.done), which reads
only initial completeness and completed-pair counts, never an arm's outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for sub in ("hop_propose", "hop_chain"):
    sys.path.insert(0, str(ROOT / "experiments" / sub))
sys.path.insert(0, str(HERE))

import connector as C
import messages
import propose_run as P
import repair_score as RS

SEED = 20261002
CONTRACT = yaml.safe_load((HERE / "contract.yaml").read_text())


def contract_text(fixture: str, pilot: bool) -> str:
    statements = CONTRACT["pilot_statements" if pilot else "statements"]
    return f"{CONTRACT['generic']}\nEvidence statement: {statements[fixture]}"


def config(fixture: str, pilot: bool, index: int, run_dir: Path, phase: str,
           snapshot: Path | None):
    cfg = P.session_config(fixture, pilot, index, run_dir, phase, snapshot)
    cfg.session_id = f"{RS.PROTOCOL}/{fixture}/i{index}/{run_dir.name}"
    cfg.contract = contract_text(fixture, pilot)
    return cfg


def _meta(run_dir: Path, args, extra: dict, cmd: list[str], code, seconds) -> None:
    meta = {"protocol": RS.PROTOCOL, "harness": args.harness, "model": args.model,
            "effort": args.effort, "max_budget_usd": args.budget_usd, "timeout": args.timeout,
            "exit": code, "seconds": seconds, "served_session": P.served_session(run_dir),
            "cost_usd": P.cost_of(run_dir), "agent_environment": P.agent_environment(run_dir),
            "cmd": ["claude", "-p", "<message elided>", *cmd[3:]], **extra}
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))


def _retryable(run_dir: Path) -> int | None:
    """Next attempt number for an INFRA_INVALID run, None when it must not be rerun."""
    if not (run_dir / "meta.json").exists():
        return 1
    validity, _ = P.classify(run_dir)
    if validity != P.INFRA_INVALID:
        return None
    if json.loads((run_dir / "meta.json").read_text()).get("attempt", 1) >= P.MAX_ATTEMPTS:
        return None
    return P.archive(run_dir)


def run_parent(fixture: str, index: int, args, block: Path) -> str:
    pdir = block / "initial"
    while (attempt := _retryable(pdir)) is not None:
        workdir = P.isolated_workdir()
        session_id = str(uuid.uuid4())
        mcp = P.write_config(config(fixture, args.pilot, index, pdir, "initial", None), pdir)
        cmd = P.claude_cmd(P.PROMPT, mcp, args, session_id=session_id, resume=None)
        code, seconds = P.execute(cmd, workdir, pdir, args.timeout)
        _meta(pdir, args, {"role": "initial", "fixture": fixture, "index": index,
                           "attempt": attempt, "session_id": session_id, "workdir": str(workdir),
                           "prompt_sha256": hashlib.sha256(P.PROMPT.encode()).hexdigest(),
                           "contract_sha256": hashlib.sha256(
                               contract_text(fixture, args.pilot).encode()).hexdigest()},
              cmd, code, seconds)
        if P.classify(pdir)[0] != P.INFRA_INVALID:
            shutil.copyfile(pdir / "state.json", pdir / "snapshot.json")
            (pdir / "snapshot.sha256").write_text(P.sha256(pdir / "snapshot.json") + "\n")
            break
        shutil.rmtree(workdir, ignore_errors=True)
        if "usage_limit" in P.classify(pdir)[1]:
            break
    validity, reason = P.classify(pdir)
    return f"{validity}:{reason}"


def run_child(fixture: str, index: int, arm: str, args, block: Path) -> str:
    pdir, cdir = block / "initial", block / arm
    parent = json.loads((pdir / "meta.json").read_text())
    while (attempt := _retryable(cdir)) is not None:
        workdir = Path(parent["workdir"])
        workdir.mkdir(exist_ok=True)
        cdir.mkdir(parents=True, exist_ok=True)
        snapshot = cdir / "initial_state.json"
        shutil.copyfile(pdir / "snapshot.json", snapshot)
        snapshot_sha = P.sha256(snapshot)
        mcp = P.write_config(config(fixture, args.pilot, index, cdir, "final", snapshot), cdir)
        message = messages.message(arm)
        cmd = P.claude_cmd(message, mcp, args, session_id=None, resume=parent["session_id"])
        code, seconds = P.execute(cmd, workdir, cdir, args.timeout)
        _meta(cdir, args, {"role": arm, "fixture": fixture, "index": index, "attempt": attempt,
                           "parent_session": parent["session_id"],
                           "snapshot_sha256_at_start": snapshot_sha,
                           "message_sha256": hashlib.sha256(message.encode()).hexdigest()},
              cmd, code, seconds)
        (cdir / "message.txt").write_text(message)
        if P.classify(cdir)[0] != P.INFRA_INVALID or "usage_limit" in P.classify(cdir)[1]:
            break
    validity, reason = P.classify(cdir)
    return f"{validity}:{reason}"


def fork(fixture: str, index: int, args, block: Path) -> list[str]:
    pdir = block / "initial"
    parent_file = P.agent_session_file(json.loads((pdir / "meta.json").read_text())["session_id"])
    parent_sha = P.sha256(parent_file) if parent_file else None
    with ThreadPoolExecutor(max_workers=len(RS.ARMS)) as pool:
        statuses = list(pool.map(lambda arm: run_child(fixture, index, arm, args, block), RS.ARMS))
    isolation = {
        "parent_session_file": str(parent_file) if parent_file else None,
        "parent_session_sha256_before": parent_sha,
        "parent_session_sha256_after": P.sha256(parent_file) if parent_file and parent_file.exists() else None,
        "snapshot_sha256": (pdir / "snapshot.sha256").read_text().strip(),
        "parent_state_sha256_after": P.sha256(pdir / "state.json"),
        "children": {arm: {"initial_state_sha256": P.sha256(block / arm / "initial_state.json"),
                           "served_session": P.served_session(block / arm)}
                     for arm in RS.ARMS if (block / arm / "initial_state.json").exists()},
    }
    (block / "isolation.json").write_text(json.dumps(isolation, indent=2))
    return [f"{s:28} {fixture}/{block.name}/{arm}" for arm, s in zip(RS.ARMS, statuses, strict=True)]


def cleanup(block: Path) -> None:
    meta = json.loads((block / "initial" / "meta.json").read_text())
    session_file = P.agent_session_file(meta["session_id"])
    if session_file:
        for f in session_file.parent.glob("*.jsonl"):
            shutil.copyfile(f, block / f"cli-session.{f.name}")
        memory = session_file.parent / "memory"
        if not (memory.is_dir() and any(memory.iterdir())):
            shutil.rmtree(session_file.parent, ignore_errors=True)
    shutil.rmtree(meta["workdir"], ignore_errors=True)


def run_block(fixture: str, index: int, args) -> list[str]:
    block = RS.runs_root(args.pilot) / fixture / f"i{index}"
    lines = [f"{run_parent(fixture, index, args, block):28} {fixture}/i{index}/initial"]
    if not lines[0].startswith("VALID"):
        return lines
    pdir = block / "initial"
    initial = RS.classify_submission(fixture, json.loads((pdir / "snapshot.json").read_text())["initial"],
                                     args.pilot)
    (block / "initial_class.json").write_text(json.dumps(initial, indent=1, default=list))
    lines.append(f"{'FULL' if initial['full'] else 'INCOMPLETE':28} {fixture}/i{index} initial "
                 + " ".join(f"{rev}={r['class']}" for rev, r in initial["revisions"].items()))
    if not initial["full"] or (args.pilot and args.force_fork):
        lines += fork(fixture, index, args, block)
    cleanup(block)
    return lines


def cli_version() -> str:
    out = subprocess.run(["claude", "--version"], capture_output=True, text=True, check=False)
    return out.stdout.split()[0] if out.stdout.split() else ""


def formal_config_problems(args: argparse.Namespace) -> list[str]:
    """§13.1: formal runs use exactly the frozen P-Hybrid-2 execution configuration."""
    given = {"model": args.model, "effort": args.effort, "max_budget_usd": args.budget_usd,
             "timeout": args.timeout}
    out = [f"{k}={given[k]!r} (frozen {v!r})" for k, v in RS.FORMAL.items() if given[k] != v]
    if (cli := cli_version()) != RS.FORMAL_SERVED["claude_code_version"]:
        out.append(f"claude CLI {cli!r} (frozen {RS.FORMAL_SERVED['claude_code_version']!r})")
    return out


def run(args: argparse.Namespace) -> None:
    commit, dirty = P.harness_commit()
    if dirty and not (args.pilot or args.allow_dirty):
        sys.exit("working tree is dirty; evaluation runs start from the frozen commit only")
    if problems := C.rows_problems("pilot" if args.pilot else "eval") + ([] if args.pilot else C.gate()):
        sys.exit("no session starts: " + "; ".join(problems))
    if not args.pilot and (problems := formal_config_problems(args)):
        sys.exit("no session starts: not the frozen execution configuration: " + "; ".join(problems))
    args.harness = {"commit": commit, "dirty": dirty}
    rng = random.Random(SEED)
    while True:
        active = []
        for f in RS.fixtures(args.pilot):
            records = [RS.block_record(b, f, args.pilot) for b in RS.blocks_on_disk(args.pilot, f)]
            if not RS.done(f, RS.sampling_counts(records), args.pilot):
                active.append((f, len(RS.blocks_on_disk(args.pilot, f))))
        if not active:
            print("all fixtures reached their targets", flush=True)
            return
        rng.shuffle(active)
        for fixture, index in active:
            for line in run_block(fixture, index, args):
                print(line, flush=True)
                if "usage_limit" in line:
                    print("STOP: usage limit reached; rerun later to continue", flush=True)
                    return


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--pilot", action="store_true")
    r.add_argument("--force-fork", action="store_true", help="pilot only: fork even a FULL initial")
    r.add_argument("--model", required=True)
    r.add_argument("--effort", default=None)
    r.add_argument("--budget-usd", type=float, default=3.0)
    r.add_argument("--timeout", type=int, default=1200)
    r.add_argument("--allow-dirty", action="store_true", help="never for the evaluation run")
    args = ap.parse_args()
    if args.force_fork and not args.pilot:
        ap.error("--force-fork is for the pilot only")
    run(args)


if __name__ == "__main__":
    main()
