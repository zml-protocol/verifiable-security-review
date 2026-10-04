"""Spike 1B runner: case × hypothesis × condition × repeat, for one pinned model.

    uv run python experiments/agent_verify/run.py fixtures/synthetic-notes/case.yaml \
        --model claude-haiku-4-5-20251001 --repeats 1 --hypotheses H1 --conditions forward --dry-run

Each run gets its own directory under runs/agent_verify/<protocol>/ holding
session.json (what the MCP server serves), transcript.jsonl + state.json
(written by the server), agent.jsonl/agent.stderr (the agent CLI's output) and
meta.json. Runs whose state.json is already finished are skipped, so the
matrix resumes. Changing the prompt, tools or derivation rules means a new
PROTOCOL value and a new preregistration (PREREGISTRATION.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path

from budget import LaunchGuard, run_cost
from validity import INFRA_INVALID, MAX_ATTEMPTS, agent_events, classify

from spike.gitrepo import GitRepo
from spike.models import CaseSpec, SessionConfig

ROOT = Path(__file__).resolve().parents[2]

PROTOCOL = "v2"  # v1.1 + bad_pattern fix (v1.2) + prompt arms for the path-citation A/B
HERE = Path(__file__).parent
# Arm -> agent prompt. Only the treatment arm adds the path-citation requirement.
PROMPTS = {
    "control": (HERE / "prompt.md").read_text(),
    "treatment": (HERE / "prompt_path.md").read_text(),
}
RUNS = ROOT / "runs" / "agent_verify" / PROTOCOL

# Metamorphic conditions: which original commit plays base and which plays head.
CONDITIONS = {
    "forward": ("base", "head"),
    "swapped": ("head", "base"),
    "identity_base": ("base", "base"),
    "identity_head": ("head", "head"),
}


@dataclass
class Run:
    case: CaseSpec
    repo: Path
    hypothesis_id: str
    condition: str
    agent: str
    model: str
    effort: str | None
    budget_usd: float | None
    repeat: int
    workdir: Path | None = None  # the agent's cwd; set per attempt, outside any git repo
    arm: str = "control"

    @property
    def label(self) -> str:
        effort = f"_{self.effort}" if self.effort else ""
        return f"{self.agent}_{self.model}{effort}_{self.arm}"

    @property
    def dir(self) -> Path:
        return RUNS / self.case.id / self.hypothesis_id / self.condition / self.label / f"r{self.repeat}"


def _server_spec(session_path: Path) -> tuple[str, list[str], dict[str, str]]:
    return sys.executable, ["-m", "spike.mcp_server"], {"SECREVIEW_SESSION": str(session_path)}


def claude_cmd(run: Run, session_path: Path) -> list[str]:
    command, args, env = _server_spec(session_path)
    mcp = {"mcpServers": {"secreview": {"command": command, "args": args, "env": env}}}
    mcp_path = run.dir / "mcp.json"
    mcp_path.write_text(json.dumps(mcp, indent=2))
    cmd = [
        "claude", "-p", PROMPTS[run.arm],
        "--tools", "",
        "--mcp-config", str(mcp_path), "--strict-mcp-config",
        "--allowedTools", "mcp__secreview",
        "--setting-sources", "",
        "--output-format", "stream-json", "--verbose",
        "--no-session-persistence",
        "--model", run.model,
    ]  # fmt: skip
    if run.effort:
        cmd += ["--effort", run.effort]
    if run.budget_usd:
        cmd += ["--max-budget-usd", str(run.budget_usd)]
    return cmd


def codex_cmd(run: Run, session_path: Path) -> list[str]:
    # Not part of protocol v1 and never exercised. Codex keeps its shell tool;
    # runs that use it are flagged at scoring time.
    command, args, env = _server_spec(session_path)
    cmd = [
        "codex", "exec", "--json", "--ephemeral", "--ignore-user-config",
        "--skip-git-repo-check", "-s", "read-only", "-C", str(run.workdir),
        "-c", f"mcp_servers.secreview.command={json.dumps(command)}",
        "-c", f"mcp_servers.secreview.args={json.dumps(args)}",
        "-c", f"mcp_servers.secreview.env={{SECREVIEW_SESSION={json.dumps(env['SECREVIEW_SESSION'])}}}",
    ]  # fmt: skip
    return [*cmd, "-m", run.model, PROMPTS[run.arm]]


AGENTS = {"claude": claude_cmd, "codex": codex_cmd}


def prepare(run: Run) -> tuple[Path, dict]:
    repo = GitRepo(run.repo)
    base_ref, head_ref = CONDITIONS[run.condition]
    refs = {"base": getattr(run.case, base_ref), "head": getattr(run.case, head_ref)}
    commits = {side: repo.resolve(ref) for side, ref in refs.items()}
    config = SessionConfig(
        session_id=f"{PROTOCOL}/{run.case.id}/{run.hypothesis_id}/{run.condition}/{run.label}/r{run.repeat}",
        repo=str(run.repo),
        revisions=commits,
        hypothesis=next(h for h in run.case.hypotheses if h.id == run.hypothesis_id),
        deny_paths=run.case.deny_paths,
        out_dir=str(run.dir),
    )
    run.dir.mkdir(parents=True, exist_ok=True)
    path = run.dir / "session.json"
    path.write_text(config.model_dump_json(indent=2))
    revisions = {side: {"commit": c, "tree": repo.tree(c)} for side, c in commits.items()}
    return path, revisions


def harness_provenance() -> dict:
    def git(*args: str) -> str:
        out = subprocess.run(
            ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=False
        )
        return out.stdout.strip()

    here = Path(__file__).parent
    files = [*sorted((ROOT / "src" / "spike").glob("*.py")), here / "run.py", here / "prompt.md"]
    return {
        "harness_commit": git("rev-parse", "--verify", "-q", "HEAD") or None,
        "harness_dirty": bool(git("status", "--porcelain")),
        "sha256": {
            str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files
        },
    }


def execute(run: Run, args: argparse.Namespace, context: dict, guard: LaunchGuard | None) -> str:
    """Run one slot. An attempted slot is only rerun when it is INFRA_INVALID
    (PREREGISTRATION.md §1.2); the failed attempt is archived next to it."""
    where = run.dir.relative_to(ROOT)
    attempt = 1
    if (run.dir / "meta.json").exists():
        validity, reason = classify(run.dir)
        previous = json.loads((run.dir / "meta.json").read_text()).get("attempt", 1)
        if validity != INFRA_INVALID or not args.rerun_invalid:
            return f"skip   {where} ({validity}: {reason})"
        if previous >= MAX_ATTEMPTS:
            return f"skip   {where} (INFRA_INVALID after {previous} attempts: {reason})"
        if args.dry_run:
            return f"rerun  {where} (attempt {previous + 1}, was {reason})"
        run.dir.rename(run.dir.with_name(f"{run.dir.name}.invalid{previous}"))
        attempt = previous + 1

    if args.dry_run:
        session_path, _ = prepare(run)
        run.workdir = Path("<isolated tempdir>")
        cmd = AGENTS[run.agent](run, session_path)
        return f"dry    {where}\n       {' '.join(map(repr, cmd[:12]))} …"
    if guard:
        allowed, state = guard.reserve(run.dir)
        if not allowed:
            with (RUNS / "budget_censored.jsonl").open("a") as f:
                f.write(json.dumps({"slot": str(where), "ts": time.time(), **state}) + "\n")
            return f"CENSORED       {where} (launch budget: {state})"
    try:
        return launch(run, args, context, attempt)
    finally:
        if guard:
            guard.release(run.dir)


def isolated_workdir() -> Path:
    """A fresh, empty cwd outside any git repository.

    Claude Code puts its cwd, git status and recent commits in the system
    prompt, and keys auto-memory by project; an opaque directory outside the
    harness repo keeps case ids, condition names and commit messages out of it.
    """
    workdir = Path(tempfile.mkdtemp(prefix="agent-"))
    inside = subprocess.run(
        ["git", "-C", str(workdir), "rev-parse", "--git-dir"], capture_output=True, check=False
    )
    if inside.returncode == 0 or workdir.resolve().is_relative_to(ROOT):
        shutil.rmtree(workdir)
        sys.exit(f"temp dir {workdir} is inside a git repository; set TMPDIR elsewhere")
    return workdir


def agent_environment(run_dir: Path) -> dict:
    """What the agent CLI reported about its own context (no credentials)."""
    init = next(
        (e for e in agent_events(run_dir)
         if e.get("type") == "system" and e.get("subtype") == "init"),
        {},
    )
    memory_dir = (init.get("memory_paths") or {}).get("auto")
    has_memory = bool(memory_dir) and Path(memory_dir).is_dir()
    return {
        "cwd": init.get("cwd"),
        "api_key_source": init.get("apiKeySource"),
        "tools": init.get("tools"),
        "memory_dir": memory_dir,
        "memory_files": sorted(p.name for p in Path(memory_dir).iterdir()) if has_memory else [],
        "plugins": [p.get("name") for p in init.get("plugins") or []],
        "skills_listed": len(init.get("skills") or []),
    }


def forget_agent_project(run_dir: Path) -> None:
    """Remove the per-cwd project dir Claude Code creates, if it is still empty."""
    memory_dir = agent_environment(run_dir).get("memory_dir")
    if not memory_dir:
        return
    for d in (Path(memory_dir), Path(memory_dir).parent):
        try:
            d.rmdir()  # only ever removes an empty directory
        except OSError:
            return


def slot_of(run: Run) -> str:
    return f"{run.case.id}/{run.hypothesis_id}/{run.condition}/r{run.repeat}"


def blocks_of(runs: list[Run]) -> list[list[Run]]:
    """Group consecutive runs of the same slot (one per arm) into a block."""
    blocks: list[list[Run]] = []
    for run in runs:
        if blocks and slot_of(blocks[-1][0]) == slot_of(run):
            blocks[-1].append(run)
        else:
            blocks.append([run])
    return blocks


def run_in_blocks(runs: list[Run], fn, jobs: int, stop=lambda lines: False):
    """Launch each block's runs together and finish the block before starting the next.

    This is the temporal matching of PREREGISTRATION.md §8.1: a control and its
    treatment always run side by side, however long either takes. `stop` sees
    each finished block's lines and can end the batch there.
    """
    for block in blocks_of(runs):
        with ThreadPoolExecutor(max_workers=max(1, min(jobs, len(block)))) as pool:
            lines = list(pool.map(fn, block))
        yield from lines
        if stop(lines):
            yield "STOP           usage limit reached; remaining blocks were not launched"
            return


def read_order(path: Path) -> list[tuple[str, str]]:
    """(arm, slot) pairs from a preregistered order file; `#` starts a comment."""
    pairs = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            arm, slot = line.split()
            pairs.append((arm, slot))
    return pairs


def launch(run: Run, args: argparse.Namespace, context: dict, attempt: int) -> str:
    where = run.dir.relative_to(ROOT)
    session_path, revisions = prepare(run)
    run.workdir = isolated_workdir()
    cmd = AGENTS[run.agent](run, session_path)
    started = time.time()
    with (run.dir / "agent.jsonl").open("w") as out, (run.dir / "agent.stderr").open("w") as err:
        try:
            code = subprocess.run(
                cmd, cwd=run.workdir, stdout=out, stderr=err, timeout=args.timeout, check=False
            ).returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    shutil.rmtree(run.workdir, ignore_errors=True)
    forget_agent_project(run.dir)
    meta = {
        "protocol": PROTOCOL,
        "attempt": attempt,
        "agent": run.agent,
        "model": run.model,
        "effort": run.effort,
        "max_budget_usd": run.budget_usd,
        "timeout": args.timeout,
        "condition": run.condition,
        "repeat": run.repeat,
        "revisions": revisions,
        **context,
        "agent_environment": agent_environment(run.dir),
        "exit": code,
        "seconds": round(time.time() - started, 1),
        "arm": run.arm,
        "prompt_sha256": hashlib.sha256(PROMPTS[run.arm].encode()).hexdigest(),
        "cmd": cmd[:1] + ["<prompt elided>" if c == PROMPTS[run.arm] else c for c in cmd[1:]],
    }
    (run.dir / "meta.json").write_text(json.dumps(meta, indent=2))
    if run.budget_usd:
        cost = run_cost(run.dir, run.budget_usd)
        meta |= {"cost_usd": cost, "overshoot": cost > run.budget_usd}
        (run.dir / "meta.json").write_text(json.dumps(meta, indent=2))
    validity, reason = classify(run.dir)
    return f"{validity:13}  {where} {reason} exit={code} {meta['seconds']}s"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("cases", nargs="+", type=Path, help="case.yaml files")
    ap.add_argument("--hypotheses", nargs="*", help="default: all in each case")
    ap.add_argument("--conditions", nargs="*", default=list(CONDITIONS), choices=list(CONDITIONS))
    ap.add_argument("--agent", default="claude", choices=list(AGENTS),
                    help="codex is not part of protocol v1")
    ap.add_argument("--model", required=True, help="pinned model id, e.g. claude-sonnet-5")
    ap.add_argument("--effort", help="claude --effort level (omit for models without effort)")
    ap.add_argument("--max-budget-usd", type=float, help="per-run spend cap")
    ap.add_argument("--total-budget-usd", type=float,
                    help="launch-budget ceiling across all attempts of this model label (§3.6)")
    ap.add_argument("--slot", action="append", default=[],
                    help="run only these slots, in this order: <case>/<hyp>/<condition>/r<k>")
    ap.add_argument("--arm", default="control", choices=list(PROMPTS),
                    help="prompt arm for every run (ignored with --order)")
    ap.add_argument("--order", type=Path,
                    help="preregistered '<arm> <case>/<hyp>/<condition>/r<k>' list, run in order")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=1200, help="seconds per run")
    ap.add_argument("--rerun-invalid", action="store_true",
                    help=f"rerun INFRA_INVALID slots (at most {MAX_ATTEMPTS} attempts in total)")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="run from uncommitted code; such runs are outside the preregistration")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    provenance = harness_provenance()
    if provenance["harness_dirty"] and not (args.dry_run or args.allow_dirty):
        sys.exit("working tree has uncommitted changes: commit first, or pass --allow-dirty")

    if args.total_budget_usd and not args.max_budget_usd:
        sys.exit("--total-budget-usd needs --max-budget-usd (the per-run reservation)")

    runs = []
    for case_path in args.cases:
        case = CaseSpec.load(case_path)
        if not case.repo.path:
            sys.exit(f"{case.id}: repo.path is not set (clone the repo first)")
        repo = ROOT / case.repo.path
        for h in case.hypotheses:
            if args.hypotheses and h.id not in args.hypotheses:
                continue
            for cond in args.conditions:
                for k in range(args.repeats):
                    runs.append(Run(case, repo, h.id, cond, args.agent, args.model,
                                    args.effort, args.max_budget_usd, k, arm=args.arm))
    if args.order:
        by_slot = {f"{r.case.id}/{r.hypothesis_id}/{r.condition}/r{r.repeat}": r for r in runs}
        order = read_order(args.order)
        missing = [s for _, s in order if s not in by_slot]
        if missing:
            sys.exit(f"unknown slots in {args.order} (check --conditions/--repeats): {missing[:5]}")
        runs = [replace(by_slot[slot], arm=arm) for arm, slot in order]
    if args.slot:
        by_slot = {f"{r.case.id}/{r.hypothesis_id}/{r.condition}/r{r.repeat}": r for r in runs}
        missing = [s for s in args.slot if s not in by_slot]
        if missing:
            sys.exit(f"unknown slots (check --conditions/--repeats): {missing}")
        runs = [by_slot[s] for s in args.slot]

    version = subprocess.run(
        [args.agent, "--version"], capture_output=True, text=True, check=False
    ).stdout.strip()
    context = {"cli_version": version, **provenance}
    print(f"{len(runs)} slots  protocol={PROTOCOL}  {args.agent} {version}  "
          f"harness={str(provenance['harness_commit'])[:12]}{' DIRTY' if provenance['harness_dirty'] else ''}")
    guard = None
    if args.total_budget_usd and runs:
        # One ceiling for the whole experiment: every arm of this model/effort shares it.
        family = runs[0].label.rsplit("_", 1)[0] + "_*"
        guard = LaunchGuard(RUNS, family, args.max_budget_usd, args.total_budget_usd)
    def one(r: Run) -> str:
        return execute(r, args, context, guard)

    if args.order:
        # An exhausted subscription fails every later attempt in seconds and would
        # burn their rerun budget (§1.2), so the batch stops at the first such block.
        def usage_limited(lines: list[str]) -> bool:
            return any(" usage_limit " in line for line in lines)

        for line in run_in_blocks(runs, one, args.jobs, stop=usage_limited):
            print(line, flush=True)
    else:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for line in pool.map(one, runs):
                print(line, flush=True)


if __name__ == "__main__":
    main()
