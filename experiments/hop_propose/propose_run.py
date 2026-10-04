"""P-Hybrid-2 runner (PREREGISTRATION.md §11): shared initial proposal -> immutable snapshot ->
two forks of the same agent session (control / treatment) -> one revision each.

    uv run python experiments/hop_propose/propose_run.py order --out experiments/hop_propose/order.txt
    uv run python experiments/hop_propose/propose_run.py run --order experiments/hop_propose/order.txt \
        --model claude-sonnet-5 --effort high
    uv run python experiments/hop_propose/propose_run.py run --pilot --model claude-haiku-4-5-20251001

A block is one (fixture, repeat): the parent session proposes and locks the initial hops;
its state is snapshotted; both arms then resume the parent with `--fork-session` at the
same time, each with its own copy of the snapshot. An INFRA_INVALID process is archived and
rerun (§1.2): a parent from scratch, a child as a new fork of the same parent.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import shutil
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "agent_verify"))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import feedback
from run import agent_environment, isolated_workdir
from validity import INFRA_INVALID, MAX_ATTEMPTS, agent_events, classify

from spike import hops as hoplib
from spike.gitrepo import GitRepo
from spike.hop_session import HopConfig
from spike.models import CaseSpec

PROTOCOL = "h2"
ARMS = ("control", "treatment")
PROMPT = (HERE / "prompt.md").read_text()
RELATIONS = yaml.safe_load((ROOT / "experiments/hop_verify/relations.yaml").read_text())["relations"]
VOCABULARY = yaml.safe_load((HERE / "vocabulary.yaml").read_text())
CASES = yaml.safe_load((HERE / "cases.yaml").read_text())
FROZEN = HERE / "frozen"
SEED = 20260929
REPEATS = 5


def runs_root(pilot: bool) -> Path:
    return ROOT / "runs" / "hop_propose" / (f"{PROTOCOL}-pilot" if pilot else PROTOCOL)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analysis_path(fixture: str, revision: str) -> Path:
    return FROZEN / f"{fixture}.{revision}.json.gz"


def load_analysis(fixture: str, revision: str) -> dict:
    return json.loads(gzip.decompress(analysis_path(fixture, revision).read_bytes()))


# ---- configs and commands ----------------------------------------------------------


def case_of(fixture: str, pilot: bool) -> tuple[dict, CaseSpec]:
    entry = CASES["pilot" if pilot else "eval"][fixture]
    return entry, CaseSpec.load(ROOT / entry["case"])


def session_config(fixture: str, pilot: bool, repeat: int, run_dir: Path, phase: str,
                   snapshot: Path | None) -> HopConfig:
    entry, case = case_of(fixture, pilot)
    return HopConfig(
        session_id=f"{PROTOCOL}/{fixture}/r{repeat}/{run_dir.name}",
        repo=str(ROOT / case.repo.path),
        revisions={"base": case.base, "head": case.head},
        hypothesis=next(h for h in case.hypotheses if h.id == entry["hypothesis"]),
        deny_paths=case.deny_paths,
        out_dir=str(run_dir),
        language=entry["language"],
        phase=phase,
        relations=RELATIONS,
        vocabulary=VOCABULARY,
        analysis={rev: str(analysis_path(fixture, rev)) for rev in ("base", "head")},
        initial_snapshot=str(snapshot) if snapshot else None,
    )


def write_config(config: HopConfig, run_dir: Path) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    session = run_dir / "session.json"
    session.write_text(config.model_dump_json(indent=2))
    mcp = {"mcpServers": {"secreview": {
        "command": sys.executable, "args": ["-m", "spike.hop_mcp_server"],
        "env": {"SECREVIEW_SESSION": str(session)}}}}
    (run_dir / "mcp.json").write_text(json.dumps(mcp, indent=2))
    return run_dir / "mcp.json"


def claude_cmd(message: str, mcp: Path, args: argparse.Namespace, *, session_id: str | None,
               resume: str | None) -> list[str]:
    cmd = ["claude", "-p", message]
    if resume:
        cmd += ["--resume", resume, "--fork-session"]
    else:
        cmd += ["--session-id", session_id]
    cmd += [
        "--tools", "",
        "--mcp-config", str(mcp), "--strict-mcp-config",
        "--allowedTools", "mcp__secreview",
        "--setting-sources", "",
        "--output-format", "stream-json", "--verbose",
        "--model", args.model,
    ]  # fmt: skip
    if args.effort:
        cmd += ["--effort", args.effort]
    cmd += ["--max-budget-usd", str(args.budget_usd)]
    return cmd


def agent_session_file(session_id: str) -> Path | None:
    """Where Claude Code persisted a session (keyed by cwd); None when absent."""
    found = list((Path.home() / ".claude" / "projects").glob(f"*/{session_id}.jsonl"))
    return found[0] if len(found) == 1 else None


def execute(cmd: list[str], cwd: Path, run_dir: Path, timeout: int) -> tuple[object, float]:
    started = time.time()
    with (run_dir / "agent.jsonl").open("w") as out, (run_dir / "agent.stderr").open("w") as err:
        try:
            code = subprocess.run(cmd, cwd=cwd, stdout=out, stderr=err, timeout=timeout,
                                  check=False).returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    return code, round(time.time() - started, 1)


def cost_of(run_dir: Path) -> float | None:
    results = [e for e in agent_events(run_dir) if e.get("type") == "result"]
    return results[-1].get("total_cost_usd") if results else None


def served_session(run_dir: Path) -> str | None:
    init = next((e for e in agent_events(run_dir)
                 if e.get("type") == "system" and e.get("subtype") == "init"), {})
    return init.get("session_id")


def archive(run_dir: Path) -> int:
    """Move an INFRA_INVALID attempt aside; return the number of the next attempt."""
    attempt = json.loads((run_dir / "meta.json").read_text()).get("attempt", 1)
    run_dir.rename(run_dir.with_name(f"{run_dir.name}.invalid{attempt}"))
    return attempt + 1


# ---- one block ---------------------------------------------------------------------


def text_reader(case: CaseSpec):
    repo = GitRepo(ROOT / case.repo.path)
    commits = {"base": repo.resolve(case.base), "head": repo.resolve(case.head)}

    def text_of(revision: str, file: str) -> str | None:
        data = repo.read_blob(commits[revision], file)
        return None if data is None else data.decode("utf-8", errors="replace")

    return text_of


def verdicts(initial: list[dict], fixture: str, pilot: bool) -> list[tuple[str, str]]:
    """The frozen verifier's state for each locked initial hop, in hop order."""
    entry, case = case_of(fixture, pilot)
    text_of = text_reader(case)
    out = []
    for hop in initial:
        canonical = {k: hop[k] for k in ("revision", "relation", "from", "to")}
        analysis = load_analysis(fixture, hop["revision"])
        resolved = hoplib.resolve(canonical, text_of, RELATIONS, analysis, entry["language"])
        out.append((hop["id"], hoplib.verdict(canonical, resolved, RELATIONS, analysis)))
    return out


def run_parent(fixture: str, repeat: int, args: argparse.Namespace, block: Path) -> str:
    pdir = block / "initial"
    attempt = 1
    if (pdir / "meta.json").exists():
        validity, reason = classify(pdir)
        if validity != INFRA_INVALID:
            return f"{validity}:{reason}"
        if json.loads((pdir / "meta.json").read_text()).get("attempt", 1) >= MAX_ATTEMPTS:
            return f"{INFRA_INVALID}:{reason}:exhausted"
        attempt = archive(pdir)
    workdir = isolated_workdir()
    session_id = str(uuid.uuid4())
    mcp = write_config(session_config(fixture, args.pilot, repeat, pdir, "initial", None), pdir)
    cmd = claude_cmd(PROMPT, mcp, args, session_id=session_id, resume=None)
    code, seconds = execute(cmd, workdir, pdir, args.timeout)
    meta = {"protocol": PROTOCOL, "harness": args.harness, "role": "initial", "fixture": fixture, "repeat": repeat,
            "attempt": attempt, "model": args.model, "effort": args.effort,
            "max_budget_usd": args.budget_usd, "timeout": args.timeout, "exit": code,
            "seconds": seconds, "session_id": session_id, "workdir": str(workdir),
            "served_session": served_session(pdir), "cost_usd": cost_of(pdir),
            "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
            "agent_environment": agent_environment(pdir),
            "cmd": ["claude", "-p", "<prompt elided>", *cmd[3:]]}
    (pdir / "meta.json").write_text(json.dumps(meta, indent=2))
    validity, reason = classify(pdir)
    if validity == INFRA_INVALID:
        shutil.rmtree(workdir, ignore_errors=True)
        return f"{validity}:{reason}"
    # the immutable snapshot both forks start from
    shutil.copyfile(pdir / "state.json", pdir / "snapshot.json")
    (pdir / "snapshot.sha256").write_text(sha256(pdir / "snapshot.json") + "\n")
    return f"{validity}:{reason}"


def run_child(fixture: str, repeat: int, arm: str, args: argparse.Namespace, block: Path,
              verdict_rows: list[tuple[str, str]]) -> str:
    pdir, cdir = block / "initial", block / arm
    attempt = 1
    if (cdir / "meta.json").exists():
        validity, reason = classify(cdir)
        if validity != INFRA_INVALID:
            return f"{validity}:{reason}"
        if json.loads((cdir / "meta.json").read_text()).get("attempt", 1) >= MAX_ATTEMPTS:
            return f"{INFRA_INVALID}:{reason}:exhausted"
        attempt = archive(cdir)
    parent = json.loads((pdir / "meta.json").read_text())
    workdir = Path(parent["workdir"])
    workdir.mkdir(exist_ok=True)  # the fork is looked up by the parent's cwd
    cdir.mkdir(parents=True)
    snapshot = cdir / "initial_state.json"
    shutil.copyfile(pdir / "snapshot.json", snapshot)
    snapshot_sha = sha256(snapshot)
    mcp = write_config(session_config(fixture, args.pilot, repeat, cdir, "final", snapshot), cdir)
    message = feedback.message(arm, verdict_rows)
    cmd = claude_cmd(message, mcp, args, session_id=None, resume=parent["session_id"])
    code, seconds = execute(cmd, workdir, cdir, args.timeout)
    meta = {"protocol": PROTOCOL, "harness": args.harness, "role": arm, "fixture": fixture, "repeat": repeat,
            "attempt": attempt, "model": args.model, "effort": args.effort,
            "max_budget_usd": args.budget_usd, "timeout": args.timeout, "exit": code,
            "seconds": seconds, "parent_session": parent["session_id"],
            "served_session": served_session(cdir), "cost_usd": cost_of(cdir),
            "snapshot_sha256_at_start": snapshot_sha,
            "message_sha256": hashlib.sha256(message.encode()).hexdigest(),
            "feedback": verdict_rows if arm == "treatment" else None,
            "agent_environment": agent_environment(cdir),
            "cmd": ["claude", "-p", "<message elided>", *cmd[3:]]}
    (cdir / "meta.json").write_text(json.dumps(meta, indent=2))
    (cdir / "message.txt").write_text(message)
    validity, reason = classify(cdir)
    return f"{validity}:{reason}"


def run_block(fixture: str, repeat: int, args: argparse.Namespace) -> list[str]:
    block = runs_root(args.pilot) / fixture / f"r{repeat}"
    lines = []
    parent_status = run_parent(fixture, repeat, args, block)
    lines.append(f"{parent_status:28} {fixture}/r{repeat}/initial")
    if parent_status.startswith(INFRA_INVALID):
        return lines
    pdir = block / "initial"
    initial = json.loads((pdir / "snapshot.json").read_text())["initial"] or []
    verdict_rows = verdicts(initial, fixture, args.pilot)
    (pdir / "verdicts.json").write_text(json.dumps(verdict_rows, indent=1))
    parent_file = agent_session_file(json.loads((pdir / "meta.json").read_text())["session_id"])
    parent_sha = sha256(parent_file) if parent_file else None
    with ThreadPoolExecutor(max_workers=len(ARMS)) as pool:
        statuses = list(pool.map(
            lambda arm: run_child(fixture, repeat, arm, args, block, verdict_rows), ARMS))
    for arm, status in zip(ARMS, statuses, strict=True):
        lines.append(f"{status:28} {fixture}/r{repeat}/{arm}")
    isolation = {
        "parent_session_file": str(parent_file) if parent_file else None,
        "parent_session_sha256_before": parent_sha,
        "parent_session_sha256_after": sha256(parent_file) if parent_file and parent_file.exists() else None,
        "snapshot_sha256": (pdir / "snapshot.sha256").read_text().strip(),
        "parent_state_sha256_after": sha256(pdir / "state.json"),
        "children": {arm: {"initial_state_sha256": sha256(block / arm / "initial_state.json"),
                           "served_session": served_session(block / arm)}
                     for arm in ARMS if (block / arm / "initial_state.json").exists()},
    }
    (block / "isolation.json").write_text(json.dumps(isolation, indent=2))
    # keep the CLI's own session files with the run, then remove its per-cwd project dir
    if parent_file:
        project = parent_file.parent
        for f in project.glob("*.jsonl"):
            shutil.copyfile(f, block / f"cli-session.{f.name}")
        memory = project / "memory"
        if not (memory.is_dir() and any(memory.iterdir())):
            shutil.rmtree(project, ignore_errors=True)
    workdir = Path(json.loads((pdir / "meta.json").read_text())["workdir"])
    shutil.rmtree(workdir, ignore_errors=True)
    return lines


# ---- order and main -------------------------------------------------------------------


def order(args: argparse.Namespace) -> None:
    blocks = [(f, r) for r in range(REPEATS) for f in sorted(CASES["eval"])]
    rng = random.Random(SEED)
    rounds = [blocks[i:i + len(CASES["eval"])] for i in range(0, len(blocks), len(CASES["eval"]))]
    for rnd in rounds:
        rng.shuffle(rnd)
    args.out.write_text("".join(f"{f} r{r}\n" for rnd in rounds for f, r in rnd))
    print(f"{args.out}: {len(blocks)} blocks")


def read_order(path: Path) -> list[tuple[str, int]]:
    out = []
    for line in path.read_text().split("\n"):
        if line.strip():
            f, r = line.split()
            out.append((f, int(r[1:])))
    return out


def harness_commit() -> tuple[str, bool]:
    def git(*a: str) -> str:
        return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True,
                              check=False).stdout.strip()

    return git("rev-parse", "HEAD"), bool(git("status", "--porcelain"))


def run(args: argparse.Namespace) -> None:
    commit, dirty = harness_commit()
    if dirty and not (args.pilot or args.allow_dirty):
        sys.exit("working tree is dirty; evaluation runs start from the frozen commit only")
    args.harness = {"commit": commit, "dirty": dirty}
    blocks = ([(f, 0) for f in sorted(CASES["pilot"])] if args.pilot else read_order(args.order))
    for fixture, rev in ((f, r) for f in {b[0] for b in blocks} for r in ("base", "head")):
        if not analysis_path(fixture, rev).exists():
            sys.exit(f"missing frozen analysis {analysis_path(fixture, rev)}")
    if args.only:
        blocks = [b for b in blocks if f"{b[0]}/r{b[1]}" in args.only]
    for fixture, repeat in blocks:
        for line in run_block(fixture, repeat, args):
            print(line, flush=True)
            if "usage_limit" in line:
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
    r.add_argument("--only", nargs="*", help="fixture/rN blocks to (re)run")
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
