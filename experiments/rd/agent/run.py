"""Run the frozen RD v2 A -> B -> C conversations.

Formal use (after ``freeze.py write`` and review)::

    uv run python experiments/rd/agent/run.py --all

One fresh conversation is created per task.  Its three phases resume sequentially
with phase-specific MCP surfaces; a task is retried from A only for an infrastructure
failure before usable agent interaction.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for directory in (HERE, ROOT / "experiments" / "agent_verify"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from validity import agent_events  # noqa: E402

import tasks  # noqa: E402
from session import RDConfig  # noqa: E402


def _local_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local module {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


freeze = _local_module("rd_agent_v2_freeze_for_runner", "freeze.py")

PROTOCOL = "rd-v2"
MODEL = "claude-sonnet-5"
EFFORT = "high"
CLI_VERSION = "2.1.280"
PHASES = ("a", "b", "c")
PHASE_TOOLS = {
    "a": {"get_task", "list_files", "read_code", "search_code", "find_symbol",
          "changed_files", "diff_file", "map_location", "submit_requirements"},
    "b": {"get_task", "list_files", "read_code", "search_code", "find_symbol",
          "changed_files", "diff_file", "map_location", "check_hop", "submit_evidence"},
    "c": {"get_task", "submit_conclusion"},
}
# Claude Code reports and enforces spend cumulatively across a resumed session.
# The scientific intervention is still an incremental $3/$3/$1 allocation, so the
# CLI must receive cumulative caps of $3/$6/$7 for A/B/C respectively.
PHASE_BUDGET = {"a": 3.0, "b": 3.0, "c": 1.0}
SESSION_CAP = {"a": 3.0, "b": 6.0, "c": 7.0}
TIMEOUT = {"a": 1200, "b": 1800, "c": 600}
CEILING = 42.0
MAX_ATTEMPTS = 3
RUNS = ROOT / "runs" / "rd" / "agent" / PROTOCOL
PROMPTS = {phase: (HERE / f"prompt-{phase}.md").read_text() for phase in PHASES}
_API_ERROR = re.compile(r"API Error|overloaded|rate.?limit|\b5\d\d\b|ECONNRESET|ETIMEDOUT|Connection error|network",
                        re.IGNORECASE)
_USAGE_LIMIT = re.compile(r"hit your .*limit|usage limit|weekly limit|limit reached", re.IGNORECASE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                          check=False).stdout.strip()


def cli_version() -> str:
    out = subprocess.run(["claude", "--version"], capture_output=True, text=True, check=False)
    return out.stdout.split()[0] if out.stdout.split() else ""


def auth_preflight() -> dict:
    """Verify local Claude authentication without retaining account identifiers."""
    out = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True,
                         check=False)
    try:
        status = json.loads(out.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError("Claude auth status was not valid JSON") from e
    if out.returncode or not status.get("loggedIn"):
        raise RuntimeError("Claude CLI is not logged in")
    return {"logged_in": True, "auth_method": status.get("authMethod"),
            "api_provider": status.get("apiProvider"),
            "subscription_type": status.get("subscriptionType")}


def network_preflight() -> dict:
    """Fail before measured attempts when the Anthropic endpoint is unreachable."""
    request = urllib.request.Request("https://api.anthropic.com", method="HEAD",
                                     headers={"User-Agent": "secreview-rd-preflight/2"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = response.status
    except urllib.error.HTTPError as e:
        # An HTTP response, including the expected root-path 404, proves transport reachability.
        status = e.code
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(f"Anthropic endpoint unreachable: {e}") from e
    return {"endpoint": "api.anthropic.com", "http_status": status}


async def _stdio_tool_names(mcp_path: Path) -> set[str]:
    spec = json.loads(mcp_path.read_text())["mcpServers"]["secreview"]
    server = StdioServerParameters(command=spec["command"], args=spec["args"], env=spec["env"])
    async with Client(server, mode="legacy", read_timeout_seconds=10) as client:
        return {tool.name for tool in (await client.list_tools()).tools}


def mcp_preflight(t: dict) -> dict:
    """Exercise the exact dynamic stdio MCP launch without invoking the measured model."""
    with tempfile.TemporaryDirectory(prefix="rd-agent-preflight-") as tmp:
        base = Path(tmp)
        mcp_path = write_config(t, "a", base / "phase-a", base / "artifacts", "preflight")
        try:
            names = asyncio.run(_stdio_tool_names(mcp_path))
        except Exception as e:
            raise RuntimeError(f"dynamic MCP handshake failed: {type(e).__name__}: {e}") from e
    expected = PHASE_TOOLS["a"]
    if names != expected:
        raise RuntimeError(f"dynamic MCP tool drift: expected {sorted(expected)}, got {sorted(names)}")
    return {"transport": "stdio", "tools": sorted(names)}


def isolated_workdir() -> Path:
    workdir = Path(tempfile.mkdtemp(prefix="rd-agent-"))
    inside = subprocess.run(["git", "-C", str(workdir), "rev-parse", "--git-dir"],
                            capture_output=True, check=False)
    if inside.returncode == 0 or workdir.resolve().is_relative_to(ROOT):
        shutil.rmtree(workdir, ignore_errors=True)
        raise RuntimeError("isolated workdir is inside a git repository")
    return workdir


def analysis_paths(task_id: str) -> dict[str, str]:
    return {rev: str(ROOT / "runs" / "rd" / "agent" / "analysis" / task_id / rev /
                          "analysis.json.gz") for rev in ("revision_A", "revision_B")}


def write_config(t: dict, phase: str, phase_dir: Path, artifact_dir: Path,
                 session_id: str) -> Path:
    cfg = RDConfig(
        session_id=f"{PROTOCOL}/{t['task_id']}/{session_id}/{phase}",
        task_id=t["task_id"], phase=phase, language=t["language"], claim=t["claim"],
        repo=t["repo"], revisions=t["revisions"], out_dir=str(phase_dir),
        artifact_dir=str(artifact_dir),
        analysis=(t.get("analysis", analysis_paths(t["task_id"])) if phase == "b" else {}),
    )
    phase_dir.mkdir(parents=True, exist_ok=True)
    path = phase_dir / "session.json"
    path.write_text(cfg.model_dump_json(indent=2) + "\n")
    mcp = {"mcpServers": {"secreview": {
        "command": sys.executable, "args": [str(HERE / "mcp_server.py")],
        "env": {"SECREVIEW_SESSION": str(path)},
    }}}
    mcp_path = phase_dir / "mcp.json"
    mcp_path.write_text(json.dumps(mcp, indent=2) + "\n")
    return mcp_path


def command(phase: str, mcp: Path, session_id: str) -> list[str]:
    cmd = ["claude", "-p", PROMPTS[phase]]
    cmd += (["--session-id", session_id] if phase == "a" else ["--resume", session_id])
    cmd += ["--tools", "", "--mcp-config", str(mcp), "--strict-mcp-config",
            "--allowedTools", "mcp__secreview", "--setting-sources", "",
            "--output-format", "stream-json", "--verbose", "--model", MODEL,
            "--effort", EFFORT, "--max-budget-usd", str(SESSION_CAP[phase])]
    return cmd


def result_text(event: dict) -> str:
    return " ".join(map(str, event.get("errors") or [])) + " " + str(event.get("result") or "")


def successful_tool_calls(phase_dir: Path) -> int:
    path = phase_dir / "transcript.jsonl"
    if not path.exists():
        return 0
    total = 0
    for line in path.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += "result" in event
    return total


def classify_phase(phase_dir: Path, phase: str) -> tuple[str, str]:
    """Only failures before usable interaction are retryable infrastructure failures."""
    events = agent_events(phase_dir)
    init_event = next((e for e in events
                       if e.get("type") == "system" and e.get("subtype") == "init"), None)
    tools = successful_tool_calls(phase_dir)
    results = [e for e in events if e.get("type") == "result"]
    if init_event is None:
        return "INFRA_INVALID", "agent_not_started"
    expected_tools = {f"mcp__secreview__{name}" for name in PHASE_TOOLS[phase]}
    if results:
        result = results[-1]
        text = result_text(result)
        if result.get("is_error") and _USAGE_LIMIT.search(text) and tools == 0:
            return "INFRA_INVALID", "usage_limit"
        if _API_ERROR.search(text) and tools == 0:
            return "INFRA_INVALID", "api_error"
    if tools == 0 and set(init_event.get("tools") or []) != expected_tools:
        return "INFRA_INVALID", "tool_surface_unavailable"
    if any(e.get("type") == "assistant" and (e.get("message") or {}).get("stop_reason") == "refusal"
           for e in events):
        return "VALID", "refusal"
    if results:
        result = results[-1]
        if result.get("subtype", "").startswith("error_max_"):
            return "VALID", result.get("subtype")
    meta = json.loads((phase_dir / "meta.json").read_text()) if (phase_dir / "meta.json").exists() else {}
    if meta.get("exit") == "timeout":
        return ("VALID", "timeout") if tools else ("INFRA_INVALID", "stalled_before_tool")
    artifact = phase_dir.parent / "artifacts" / f"{phase}.json"
    if artifact.exists():
        return "VALID", "locked"
    if results:
        result = results[-1]
        if result.get("subtype") == "success" and not result.get("is_error"):
            return "VALID", "completed_without_lock"
        return ("VALID", result.get("subtype") or "agent_error") if tools else \
               ("INFRA_INVALID", result.get("subtype") or "startup_error")
    return ("VALID", "ended_without_result") if tools else ("INFRA_INVALID", "agent_stalled")


def cost_of(phase_dir: Path) -> float | None:
    for event in reversed(agent_events(phase_dir)):
        if event.get("type") == "result" and event.get("total_cost_usd") is not None:
            return float(event["total_cost_usd"])
    return None


def observed_spend() -> float:
    """Return actual cumulative spend, with a conservative cap for result-less phases.

    ``total_cost_usd`` in a resumed Claude result is cumulative for that conversation;
    summing A, B and C would therefore count A three times and B twice.  Each attempt is
    a distinct conversation, so charge its largest cumulative report.  If a started phase
    produced no cost report, reserve the cumulative CLI cap recorded in its metadata.
    """
    total = 0.0
    attempts = {log.parent.parent for log in RUNS.glob("*/attempt-*/phase-*/agent.jsonl")}
    for attempt in attempts:
        charged = 0.0
        for phase_dir in attempt.glob("phase-*"):
            cost = cost_of(phase_dir)
            if cost is not None:
                charged = max(charged, cost)
                continue
            meta_path = phase_dir / "meta.json"
            meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            charged = max(charged, float(meta.get("max_budget_usd", 0)))
        total += charged
    return total


def environment(phase_dir: Path) -> dict:
    init = next((e for e in agent_events(phase_dir)
                 if e.get("type") == "system" and e.get("subtype") == "init"), {})
    memory = (init.get("memory_paths") or {}).get("auto")
    return {"cwd": init.get("cwd"), "model": init.get("model"),
            "served_session": init.get("session_id"), "tools": init.get("tools"),
            "plugins": [p.get("name") for p in init.get("plugins") or []],
            "skills_listed": len(init.get("skills") or []), "memory_dir": memory,
            "memory_files": (sorted(p.name for p in Path(memory).iterdir())
                             if memory and Path(memory).is_dir() else [])}


def session_file(session_id: str) -> Path | None:
    found = list((Path.home() / ".claude" / "projects").glob(f"*/{session_id}.jsonl"))
    return found[0] if len(found) == 1 else None


def execute_phase(t: dict, phase: str, attempt_dir: Path, workdir: Path,
                  session_id: str, harness: dict) -> tuple[str, str]:
    phase_dir = attempt_dir / f"phase-{phase}"
    if observed_spend() + PHASE_BUDGET[phase] > CEILING:
        return "BUDGET_CENSORED", f"launch ceiling ${CEILING:.0f}"
    mcp = write_config(t, phase, phase_dir, attempt_dir / "artifacts", session_id)
    cmd = command(phase, mcp, session_id)
    started = time.time()
    with (phase_dir / "agent.jsonl").open("w") as out, (phase_dir / "agent.stderr").open("w") as err:
        try:
            code = subprocess.run(cmd, cwd=workdir, stdout=out, stderr=err,
                                  timeout=TIMEOUT[phase], check=False).returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    meta = {"protocol": PROTOCOL, "task_id": t["task_id"], "phase": phase,
            "model": MODEL, "effort": EFFORT, "claude_code_version": cli_version(),
            "phase_budget_usd": PHASE_BUDGET[phase],
            "max_budget_usd": SESSION_CAP[phase], "timeout": TIMEOUT[phase], "exit": code,
            "seconds": round(time.time() - started, 1), "session_id": session_id,
            "prompt_sha256": hashlib.sha256(PROMPTS[phase].encode()).hexdigest(),
            "mcp_config_sha256": sha256(mcp), "harness": harness,
            "cost_usd": cost_of(phase_dir), "agent_environment": environment(phase_dir),
            "cmd": ["claude", "-p", "<prompt elided>", *cmd[3:]]}
    (phase_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    status, reason = classify_phase(phase_dir, phase)
    meta["validity"], meta["validity_reason"] = status, reason
    (phase_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return status, reason


def cleanup_attempt(attempt_dir: Path, workdir: Path, session_id: str) -> None:
    sf = session_file(session_id)
    if sf:
        target = attempt_dir / "cli-project"
        target.mkdir(exist_ok=True)
        for f in sf.parent.glob("*.jsonl"):
            shutil.copyfile(f, target / f.name)
        memory = sf.parent / "memory"
        if memory.is_dir():
            for f in memory.iterdir():
                if f.is_file():
                    shutil.copyfile(f, target / f"memory.{f.name}")
        shutil.rmtree(sf.parent, ignore_errors=True)
    shutil.rmtree(workdir, ignore_errors=True)


def run_attempt(t: dict, attempt: int, harness: dict) -> tuple[str, str]:
    attempt_dir = RUNS / t["task_id"] / f"attempt-{attempt}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    workdir, sid = isolated_workdir(), str(uuid.uuid4())
    result = ("VALID", "complete")
    rows = []
    try:
        for phase in PHASES:
            status, reason = execute_phase(t, phase, attempt_dir, workdir, sid, harness)
            rows.append({"phase": phase, "status": status, "reason": reason})
            print(f"{status:16} {t['task_id']}/attempt-{attempt}/{phase}: {reason}", flush=True)
            if status != "VALID" or not (attempt_dir / "artifacts" / f"{phase}.json").exists():
                result = (status, reason)
                break
    finally:
        cleanup_attempt(attempt_dir, workdir, sid)
    record = {"protocol": PROTOCOL, "task_id": t["task_id"], "attempt": attempt,
              "session_id": sid, "phases": rows, "status": result[0], "reason": result[1]}
    (attempt_dir / "attempt.json").write_text(json.dumps(record, indent=2) + "\n")
    return result


def run_task(task_id: str, harness: dict) -> tuple[str, str]:
    t = tasks.task(task_id)
    root = RUNS / task_id
    attempts = sorted(root.glob("attempt-*")) if root.exists() else []
    if attempts:
        last = json.loads((attempts[-1] / "attempt.json").read_text())
        if last["status"] != "INFRA_INVALID":
            print(f"skip             {task_id}: {last['status']} {last['reason']}", flush=True)
            return last["status"], last["reason"]
    for number in range(len(attempts) + 1, MAX_ATTEMPTS + 1):
        status, reason = run_attempt(t, number, harness)
        if status == "INFRA_INVALID" and reason == "usage_limit":
            return status, reason
        if status != "INFRA_INVALID":
            return status, reason
    return "INFRA_INVALID", "three attempts exhausted"


def preflight() -> dict:
    if cli_version() != CLI_VERSION:
        raise SystemExit(f"Claude Code {cli_version()!r}; frozen version is {CLI_VERSION!r}")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("tracked working tree is dirty; formal runs require the frozen commit")
    freeze.verify()
    for task_id in tasks.order():
        for path in analysis_paths(task_id).values():
            if not Path(path).exists():
                raise SystemExit(f"missing analysis: {path}")
    try:
        infrastructure = {"auth": auth_preflight(), "network": network_preflight(),
                          "mcp": mcp_preflight(tasks.task(tasks.order()[0]))}
    except RuntimeError as e:
        raise SystemExit(f"infrastructure preflight failed before measured attempts: {e}") from e
    return {"commit": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
            "freeze_sha256": sha256(freeze.FREEZE), "infrastructure_preflight": infrastructure}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="run every task in frozen order")
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    selected = tasks.order() if args.all else args.only
    if not selected:
        ap.error("use --all or --only task-XX ...")
    if args.dry_run:
        for task_id in selected:
            print(task_id, tasks.task(task_id)["claim"], analysis_paths(task_id))
        return
    harness = preflight()
    RUNS.mkdir(parents=True, exist_ok=True)
    for task_id in selected:
        status, reason = run_task(task_id, harness)
        if status == "BUDGET_CENSORED":
            print("STOP: frozen launch ceiling reached", flush=True)
            return
        if status == "INFRA_INVALID" and reason == "usage_limit":
            print("STOP: external usage limit; resume with the same command later", flush=True)
            return


if __name__ == "__main__":
    main()
