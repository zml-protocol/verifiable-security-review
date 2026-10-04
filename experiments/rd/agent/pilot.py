"""Prepare, run and validate the non-measured synthetic RD plumbing pilot."""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PILOT = HERE / "pilot"
for directory in (HERE, PILOT):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import analysis  # noqa: E402
import build  # noqa: E402
import run as runner  # noqa: E402

RUNS = ROOT / "runs" / "rd" / "agent" / "pilot"
RESULT = RUNS / "result.json"


def task_spec() -> dict:
    info = build.build()
    return {"task_id": "pilot-task", "fixture": "synthetic-rd-pilot", "language": "go",
            "claim": {"package": "example.invalid/rdpilot", "cwe": 78,
                      "cwe_name": "OS Command Injection"},
            "repo": info["repo"],
            "revisions": {"revision_A": info["revision_A"], "revision_B": info["revision_B"]},
            "source_provenance": info}


def prepare(force: bool = False) -> dict:
    t = task_spec()
    paths = {}
    for revision in ("revision_A", "revision_B"):
        out = RUNS / "analysis" / revision
        frozen = out / "analysis.json.gz"
        valid = False
        if frozen.exists() and not force:
            try:
                doc = json.loads(gzip.decompress(frozen.read_bytes()))
                valid = doc.get("status") == "ok" and doc.get("commit") == t["revisions"][revision]
            except (OSError, json.JSONDecodeError):
                valid = False
        if not valid:
            analysis.build_spec(t, t["task_id"], revision, out)
        paths[revision] = str(frozen)
    t["analysis"] = paths
    (RUNS / "task.json").parent.mkdir(parents=True, exist_ok=True)
    (RUNS / "task.json").write_text(json.dumps(t, indent=2) + "\n")
    return t


def run() -> tuple[str, str]:
    t = prepare()
    runner.RUNS = RUNS / "conversation"
    runner.CEILING = 7.0
    existing = sorted((runner.RUNS / t["task_id"]).glob("attempt-*"))
    attempt = len(existing) + 1
    harness = {"pilot": True, "commit": runner.git("rev-parse", "HEAD"),
               "tracked_dirty": bool(runner.git("status", "--porcelain", "--untracked-files=no"))}
    return runner.run_attempt(t, attempt, harness)


def check() -> dict:
    attempts = sorted((RUNS / "conversation" / "pilot-task").glob("attempt-*"))
    problems = []
    if not attempts:
        problems.append("pilot conversation has not run")
        attempt = RUNS / "conversation" / "pilot-task" / "attempt-0"
        phases = []
    else:
        attempt = attempts[-1]
        phases = json.loads((attempt / "attempt.json").read_text())["phases"]
        if [p["phase"] for p in phases] != ["a", "b", "c"]:
            problems.append("A/B/C did not all run sequentially")
        if any(p["status"] != "VALID" for p in phases):
            problems.append(f"non-valid phase: {phases}")
        for phase in ("a", "b", "c"):
            if not (attempt / "artifacts" / f"{phase}.json").exists():
                problems.append(f"phase {phase} did not lock")
    metas = []
    for phase in ("a", "b", "c"):
        path = attempt / f"phase-{phase}" / "meta.json"
        if path.exists():
            metas.append(json.loads(path.read_text()))
    if len(metas) == 3:
        envs = [m["agent_environment"] for m in metas]
        if len({e["cwd"] for e in envs}) != 1:
            problems.append("phases did not share one isolated cwd")
        if any(e["memory_files"] for e in envs):
            problems.append("auto-memory was non-empty")
        if any(m["model"] != runner.MODEL or m["effort"] != runner.EFFORT for m in metas):
            problems.append("model/effort drift")
        expected_budget = {"a": (3.0, 3.0), "b": (3.0, 6.0), "c": (1.0, 7.0)}
        if any((m.get("phase_budget_usd"), m.get("max_budget_usd")) != expected_budget[m["phase"]]
               for m in metas):
            problems.append("incremental/cumulative budget metadata drift")
        for meta in metas:
            phase = meta["phase"]
            expected_tools = {f"mcp__secreview__{name}" for name in runner.PHASE_TOOLS[phase]}
            if set(meta["agent_environment"].get("tools") or []) != expected_tools:
                problems.append(f"phase {phase} tool surface drift")
        c_tools = json.dumps(envs[2].get("tools") or [])
        if any(name in c_tools for name in ("read_code", "diff_file", "check_hop")):
            problems.append("phase C exposed a read or verifier tool")
    unit = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_rd_protocol.py"],
                          cwd=ROOT, capture_output=True, text=True, check=False)
    if unit.returncode:
        problems.append("deterministic protocol gate tests failed")
    result = {"schema": "rd-pilot-result/v1", "status": "PASS" if not problems else "FAIL",
              "problems": problems, "evaluated_attempt": attempt.name,
              "attempt_history": [p.name for p in attempts], "phases": phases,
              "deterministic_gate_tests": {"exit": unit.returncode, "output": unit.stdout[-1000:]},
              "synthetic_source": json.loads((RUNS / "task.json").read_text()).get("source_provenance")}
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("prepare", "run", "check"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if args.command == "prepare":
        prepare(force=args.force)
    elif args.command == "run":
        run()
        check()
    else:
        check()


if __name__ == "__main__":
    main()
