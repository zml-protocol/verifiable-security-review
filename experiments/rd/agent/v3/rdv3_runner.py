"""Run RD v3 held-out-A or formal sessions under their frozen launch envelopes.

This file performs no run on import. A measurement manifest and treatment freeze are created only
after development/pilot, before the one-shot held-out gate.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
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
ROOT = HERE.parents[3]
for directory in (HERE, ROOT / "experiments" / "agent_verify"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from validity import agent_events  # noqa: E402

import rdv3_checkpoint as checkpoint  # noqa: E402
import rdv3_contract as contract  # noqa: E402
from rdv3_session import V3Config  # noqa: E402

PROTOCOL = "rd-v3"
MODEL = "claude-sonnet-5"
EFFORT = "high"
CLI_VERSION = "2.1.280"
STAGES = ("a", "b", "c1", "c2")
PHASE = {"a": "a", "b": "b", "c1": "c", "c2": "c"}
C_STAGE = {"a": None, "b": None, "c1": "c1", "c2": "c2"}
PHASE_BUDGET = {"a": 3.0, "b": 3.0, "c1": 1.0, "c2": 0.0}
SESSION_CAP = {"a": 3.0, "b": 6.0, "c1": 7.0, "c2": 7.0}
TIMEOUT = {"a": 1200, "b": 1800, "c1": 600, "c2": 600}
PHASE_TOOLS = {
    "a": {"get_task", "list_files", "read_code", "search_code", "find_symbol",
          "changed_files", "diff_file", "map_location", "submit_requirements"},
    "b": {"get_task", "list_files", "read_code", "search_code", "find_symbol",
          "changed_files", "diff_file", "map_location", "check_hop", "submit_evidence"},
    "c1": {"get_task", "submit_effect_attribution"},
    "c2": {"get_task", "submit_cwe_taxonomy"},
}
PROMPTS = {stage: (HERE / f"prompt-{stage}.md").read_text() for stage in STAGES}
RUNS = ROOT / "runs" / "rd" / "agent" / PROTOCOL
TREATMENT_FREEZE = HERE / "treatment-freeze-v2.json"
_API_ERROR = re.compile(
    r"API Error|overloaded|rate.?limit|\b5\d\d\b|ECONNRESET|ETIMEDOUT|Connection error|network",
    re.IGNORECASE,
)
_USAGE_LIMIT = re.compile(r"hit your .*limit|usage limit|weekly limit|limit reached", re.IGNORECASE)


class RunnerError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                          check=False).stdout.strip()


def cli_version() -> str:
    result = subprocess.run(["claude", "--version"], capture_output=True, text=True, check=False)
    return result.stdout.split()[0] if result.stdout.split() else ""


def load_manifest(path: Path) -> dict:
    doc = json.loads(path.read_text())
    if doc.get("schema") != "rd-v3-run-manifest/v1" or doc.get("protocol") != PROTOCOL:
        raise RunnerError("bad RD v3 run manifest")
    mode = doc.get("mode")
    tasks = doc.get("tasks")
    if mode not in ("heldout_a", "formal") or not isinstance(tasks, list) or not tasks:
        raise RunnerError("run manifest needs a non-empty heldout_a or formal task list")
    ids = [task.get("task_id") for task in tasks]
    if any(not isinstance(task_id, str) for task_id in ids) or len(ids) != len(set(ids)):
        raise RunnerError("run manifest task ids must be unique strings")
    expected_count = 20 if mode == "heldout_a" else doc.get("formal_task_count")
    if len(tasks) != expected_count:
        raise RunnerError(f"{mode} task count drift: {len(tasks)} != {expected_count}")
    if mode == "formal":
        real = [task for task in tasks if task.get("task_kind") == "real"]
        controls = [task for task in tasks if task.get("task_kind") == "negative_control"]
        if len(real) + len(controls) != len(tasks):
            raise RunnerError("formal tasks must be real or negative_control")
        if doc.get("realized_real_tasks") != len(real):
            raise RunnerError("realized real task count drift")
        if doc.get("qualified_negative_control_tasks") != len(controls):
            raise RunnerError("qualified negative-control task count drift")
        if not 1 <= len(real) <= 6 or len(controls) > len(real):
            raise RunnerError("formal real/control counts violate the frozen bounds")
        real_ids = {task["task_id"] for task in real}
        parents = [task.get("parent_real_task_id") for task in controls]
        if any(parent not in real_ids for parent in parents) or len(parents) != len(set(parents)):
            raise RunnerError("each negative control must name a distinct manifest real task")
        languages = [task.get("language") for task in real]
        if any(language not in ("go", "python") for language in languages):
            raise RunnerError("formal real tasks must be Go or Python")
        if languages.count("go") > 3 or languages.count("python") > 3:
            raise RunnerError("formal real language count exceeds the frozen 3+3 target")
    ceiling = 60.0 if mode == "heldout_a" else 7.0 * len(tasks)
    if doc.get("launch_ceiling_usd") != ceiling:
        raise RunnerError(f"launch ceiling drift: expected ${ceiling:.0f}")
    if float(doc.get("user_authorization_usd", -1)) < ceiling:
        raise RunnerError("FORMAL_NOT_STARTED_BUDGET_AUTHORIZATION" if mode == "formal"
                          else "HELDOUT_NOT_STARTED_BUDGET_AUTHORIZATION")
    return doc


def auth_preflight() -> dict:
    result = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True,
                            check=False)
    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RunnerError("Claude auth status was not valid JSON") from exc
    if result.returncode or not status.get("loggedIn"):
        raise RunnerError("Claude CLI is not logged in")
    return {"logged_in": True, "auth_method": status.get("authMethod"),
            "api_provider": status.get("apiProvider"),
            "subscription_type": status.get("subscriptionType")}


def network_preflight() -> dict:
    request = urllib.request.Request("https://api.anthropic.com", method="HEAD",
                                     headers={"User-Agent": "secreview-rd-preflight/3"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RunnerError(f"Anthropic endpoint unreachable: {exc}") from exc
    return {"endpoint": "api.anthropic.com", "http_status": status}


async def _stdio_tool_names(mcp_path: Path) -> set[str]:
    spec = json.loads(mcp_path.read_text())["mcpServers"]["secreview"]
    server = StdioServerParameters(command=spec["command"], args=spec["args"], env=spec["env"])
    async with Client(server, mode="legacy", read_timeout_seconds=10) as client:
        return {tool.name for tool in (await client.list_tools()).tools}


def isolated_workdir() -> Path:
    workdir = Path(tempfile.mkdtemp(prefix="rd-v3-agent-"))
    inside = subprocess.run(["git", "-C", str(workdir), "rev-parse", "--git-dir"],
                            capture_output=True, check=False)
    if inside.returncode == 0 or workdir.resolve().is_relative_to(ROOT):
        shutil.rmtree(workdir, ignore_errors=True)
        raise RunnerError("isolated workdir is inside a git repository")
    return workdir


def write_config(task: dict, stage: str, stage_dir: Path, artifact_dir: Path,
                 session_id: str, treatment: dict) -> Path:
    config = V3Config(
        session_id=f"{PROTOCOL}/{task['task_id']}/{session_id}/{stage}",
        task_id=task["task_id"], phase=PHASE[stage], c_stage=C_STAGE[stage],
        language=task["language"], claim={"package": task["package"],
                                          "effect_claim": task["effect_claim"]},
        repo=task["repo"], revisions=task["revisions"],
        deny_paths=task.get("deny_paths") or [], out_dir=str(stage_dir),
        artifact_dir=str(artifact_dir), analysis=task.get("analysis") or {},
        provider_sha256=treatment.get("provider_sha256", "") if stage == "b" else "",
        relation_table_sha256=treatment.get("relation_table_sha256", "") if stage == "b" else "",
    )
    stage_dir.mkdir(parents=True, exist_ok=True)
    session_path = stage_dir / "session.json"
    session_path.write_text(config.model_dump_json(indent=2) + "\n")
    mcp = {"mcpServers": {"secreview": {
        "command": sys.executable, "args": [str(HERE / "rdv3_mcp_server.py")],
        "env": {"SECREVIEW_SESSION": str(session_path)},
    }}}
    mcp_path = stage_dir / "mcp.json"
    mcp_path.write_text(json.dumps(mcp, indent=2) + "\n")
    return mcp_path


def mcp_preflight(task: dict, stage: str, treatment: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="rd-v3-mcp-preflight-") as tmp:
        root = Path(tmp)
        artifacts = root / "artifacts"
        artifacts.mkdir()
        if stage != "a":
            a = contract.sealed({"schema": "rd-v3-preflight-a/v1",
                                 "task_id": task["task_id"], "requirements": {}})
            (artifacts / "a.json").write_text(json.dumps(a) + "\n")
        if stage in ("c1", "c2"):
            b = contract.sealed({"schema": "rd-v3-preflight-b/v1",
                                 "task_id": task["task_id"], "a_seal": a["seal"], "hops": []})
            (artifacts / "b.json").write_text(json.dumps(b) + "\n")
        if stage == "c2":
            c1 = contract.sealed({"schema": "rd-v3-preflight-c1/v1",
                                  "task_id": task["task_id"], "a_seal": a["seal"],
                                  "b_seal": b["seal"], "conclusion": {}})
            (artifacts / "c1.json").write_text(json.dumps(c1) + "\n")
        mcp = write_config(task, stage, root / stage, artifacts, "preflight", treatment)
        names = asyncio.run(_stdio_tool_names(mcp))
    expected = PHASE_TOOLS[stage]
    if names != expected:
        raise RunnerError(f"{stage} MCP drift: expected {sorted(expected)}, got {sorted(names)}")
    return {"stage": stage, "transport": "stdio", "tools": sorted(names)}


def command(stage: str, mcp: Path, session_id: str) -> list[str]:
    cmd = ["claude", "-p", PROMPTS[stage]]
    cmd += (["--session-id", session_id] if stage == "a" else ["--resume", session_id])
    cmd += ["--tools", "", "--mcp-config", str(mcp), "--strict-mcp-config",
            "--allowedTools", "mcp__secreview", "--setting-sources", "",
            "--output-format", "stream-json", "--verbose", "--model", MODEL,
            "--effort", EFFORT, "--max-budget-usd", str(SESSION_CAP[stage])]
    return cmd


def result_text(event: dict) -> str:
    return " ".join(map(str, event.get("errors") or [])) + " " + str(event.get("result") or "")


def successful_tool_calls(stage_dir: Path) -> int:
    path = stage_dir / "transcript.jsonl"
    if not path.exists():
        return 0
    total = 0
    for line in path.read_text().splitlines():
        try:
            total += "result" in json.loads(line)
        except json.JSONDecodeError:
            pass
    return total


def stage_artifact(artifact_dir: Path, stage: str) -> Path:
    return artifact_dir / {"a": "a.json", "b": "b.json", "c1": "c1.json", "c2": "c2.json"}[stage]


def classify_stage(stage_dir: Path, artifact_dir: Path, stage: str) -> tuple[str, str]:
    events = agent_events(stage_dir)
    init = next((event for event in events
                 if event.get("type") == "system" and event.get("subtype") == "init"), None)
    tools = successful_tool_calls(stage_dir)
    results = [event for event in events if event.get("type") == "result"]
    if init is None:
        return "INFRA_INVALID", "agent_not_started"
    expected = {f"mcp__secreview__{name}" for name in PHASE_TOOLS[stage]}
    if results:
        text = result_text(results[-1])
        if results[-1].get("is_error") and _USAGE_LIMIT.search(text) and tools == 0:
            return "INFRA_INVALID", "usage_limit"
        if _API_ERROR.search(text) and tools == 0:
            return "INFRA_INVALID", "api_error"
    if tools == 0 and set(init.get("tools") or []) != expected:
        return "INFRA_INVALID", "tool_surface_unavailable"
    if any(event.get("type") == "assistant"
           and (event.get("message") or {}).get("stop_reason") == "refusal" for event in events):
        return "VALID", "refusal"
    if results and results[-1].get("subtype", "").startswith("error_max_"):
        return "VALID", results[-1]["subtype"]
    meta_path = stage_dir / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    if meta.get("exit") == "timeout":
        return ("VALID", "timeout") if tools else ("INFRA_INVALID", "stalled_before_tool")
    if stage_artifact(artifact_dir, stage).exists():
        return "VALID", "locked"
    if results:
        result = results[-1]
        if result.get("subtype") == "success" and not result.get("is_error"):
            return "VALID", "completed_without_lock"
        return (("VALID", result.get("subtype") or "agent_error") if tools else
                ("INFRA_INVALID", result.get("subtype") or "startup_error"))
    return (("VALID", "ended_without_result") if tools else
            ("INFRA_INVALID", "agent_stalled"))


def cost_of(stage_dir: Path) -> float | None:
    for event in reversed(agent_events(stage_dir)):
        if event.get("type") == "result" and event.get("total_cost_usd") is not None:
            return float(event["total_cost_usd"])
    return None


def observed_spend(run_root: Path) -> float:
    total = 0.0
    attempts = {path.parent.parent for path in run_root.glob("*/attempt-*/stage-*/agent.jsonl")}
    for attempt in attempts:
        charged = 0.0
        for stage_dir in attempt.glob("stage-*"):
            cost = cost_of(stage_dir)
            if cost is not None:
                charged = max(charged, cost)
            else:
                meta = json.loads((stage_dir / "meta.json").read_text()) \
                    if (stage_dir / "meta.json").exists() else {}
                charged = max(charged, float(meta.get("max_budget_usd", 0)))
        total += charged
    return total


def environment(stage_dir: Path) -> dict:
    init = next((event for event in agent_events(stage_dir)
                 if event.get("type") == "system" and event.get("subtype") == "init"), {})
    memory = (init.get("memory_paths") or {}).get("auto")
    return {"cwd": init.get("cwd"), "model": init.get("model"),
            "served_session": init.get("session_id"), "tools": init.get("tools"),
            "plugins": [plugin.get("name") for plugin in init.get("plugins") or []],
            "skills_listed": len(init.get("skills") or []), "memory_dir": memory,
            "memory_files": (sorted(path.name for path in Path(memory).iterdir())
                             if memory and Path(memory).is_dir() else [])}


def session_file(session_id: str) -> Path | None:
    found = list((Path.home() / ".claude" / "projects").glob(f"*/{session_id}.jsonl"))
    return found[0] if len(found) == 1 else None


def execute_stage(task: dict, stage: str, attempt_dir: Path, workdir: Path,
                  session_id: str, harness: dict, treatment: dict,
                  *, run_root: Path, launch_ceiling: float, timeout: float | None = None,
                  c_elapsed_before: float = 0.0) -> tuple[str, str]:
    stage_dir = attempt_dir / f"stage-{stage}"
    artifact_dir = attempt_dir / "artifacts"
    if observed_spend(run_root) + PHASE_BUDGET[stage] > launch_ceiling:
        return "BUDGET_CENSORED", f"launch ceiling ${launch_ceiling:.0f}"
    mcp = write_config(task, stage, stage_dir, artifact_dir, session_id, treatment)
    cmd = command(stage, mcp, session_id)
    allowed_seconds = timeout if timeout is not None else TIMEOUT[stage]
    started = time.monotonic()
    with (stage_dir / "agent.jsonl").open("w") as stdout, \
            (stage_dir / "agent.stderr").open("w") as stderr:
        try:
            code = subprocess.run(cmd, cwd=workdir, stdout=stdout, stderr=stderr,
                                  timeout=allowed_seconds, check=False).returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    elapsed = time.monotonic() - started
    meta = {"protocol": PROTOCOL, "task_id": task["task_id"], "stage": stage,
            "phase": PHASE[stage], "model": MODEL, "effort": EFFORT,
            "claude_code_version": cli_version(), "phase_budget_usd": PHASE_BUDGET[stage],
            "max_budget_usd": SESSION_CAP[stage], "timeout": allowed_seconds, "exit": code,
            "seconds": round(elapsed, 3), "c_envelope_elapsed_before": c_elapsed_before,
            "c_envelope_elapsed_after": (round(c_elapsed_before + elapsed, 3)
                                         if stage in ("c1", "c2") else None),
            "session_id": session_id,
            "prompt_sha256": hashlib.sha256(PROMPTS[stage].encode()).hexdigest(),
            "mcp_config_sha256": sha256(mcp), "harness": harness,
            "cost_usd": cost_of(stage_dir), "agent_environment": environment(stage_dir),
            "cmd": ["claude", "-p", "<prompt elided>", *cmd[3:]]}
    (stage_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    status, reason = classify_stage(stage_dir, artifact_dir, stage)
    meta["validity"], meta["validity_reason"] = status, reason
    (stage_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return status, reason


def finalize_b(attempt_dir: Path) -> dict:
    artifacts = attempt_dir / "artifacts"
    partial = checkpoint.materialize(artifacts / "b-checkpoints",
                                     artifacts / "partial-checkpoint.json")
    selected = checkpoint.materialize_terminal_b(artifacts)
    return {"partial_checkpoint_seal": partial["seal"], "b_input_seal": selected["seal"],
            "b_status": selected.get("status", "FINAL_SUBMIT")}


def cleanup_attempt(attempt_dir: Path, workdir: Path, session_id: str) -> None:
    session = session_file(session_id)
    if session:
        target = attempt_dir / "cli-project"
        target.mkdir(exist_ok=True)
        for path in session.parent.glob("*.jsonl"):
            shutil.copyfile(path, target / path.name)
        memory = session.parent / "memory"
        if memory.is_dir():
            for path in memory.iterdir():
                if path.is_file():
                    shutil.copyfile(path, target / f"memory.{path.name}")
        shutil.rmtree(session.parent, ignore_errors=True)
    shutil.rmtree(workdir, ignore_errors=True)


def run_attempt(task: dict, attempt: int, mode: str, harness: dict, treatment: dict,
                run_root: Path, launch_ceiling: float) -> tuple[str, str]:
    attempt_dir = run_root / task["task_id"] / f"attempt-{attempt}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    workdir, session_id = isolated_workdir(), str(uuid.uuid4())
    rows, result = [], ("VALID", "complete")
    try:
        status, reason = execute_stage(task, "a", attempt_dir, workdir, session_id,
                                       harness, treatment, run_root=run_root,
                                       launch_ceiling=launch_ceiling)
        rows.append({"stage": "a", "status": status, "reason": reason})
        if status != "VALID" or not (attempt_dir / "artifacts" / "a.json").exists():
            result = (status, reason)
        elif mode == "heldout_a":
            result = ("VALID", "a_locked")
        else:
            status, reason = execute_stage(task, "b", attempt_dir, workdir, session_id,
                                           harness, treatment, run_root=run_root,
                                           launch_ceiling=launch_ceiling)
            rows.append({"stage": "b", "status": status, "reason": reason})
            if status != "VALID":
                result = (status, reason)
            else:
                try:
                    b_summary = finalize_b(attempt_dir)
                    rows[-1].update(b_summary)
                except Exception as exc:
                    result = ("HARNESS_INVALID", f"B checkpoint finalization failed: {exc}")
                if result[0] == "VALID":
                    c_started = time.monotonic()
                    status, reason = execute_stage(task, "c1", attempt_dir, workdir, session_id,
                                                   harness, treatment, run_root=run_root,
                                                   launch_ceiling=launch_ceiling, timeout=600)
                    rows.append({"stage": "c1", "status": status, "reason": reason})
                    if status != "VALID":
                        result = (status, reason)
                    elif not (attempt_dir / "artifacts" / "c1.json").exists():
                        result = ("VALID", "C1_MISSING_C2_NOT_REACHED")
                    else:
                        elapsed = time.monotonic() - c_started
                        remaining = max(0.0, 600.0 - elapsed)
                        if remaining <= 0:
                            result = ("VALID", "C2_MISSING")
                        else:
                            status, reason = execute_stage(
                                task, "c2", attempt_dir, workdir, session_id, harness, treatment,
                                run_root=run_root, launch_ceiling=launch_ceiling,
                                timeout=remaining, c_elapsed_before=elapsed)
                            rows.append({"stage": "c2", "status": status, "reason": reason})
                            if status != "VALID":
                                result = (status, reason)
                            elif not (attempt_dir / "artifacts" / "c2.json").exists():
                                result = ("VALID", "C2_MISSING")
    finally:
        cleanup_attempt(attempt_dir, workdir, session_id)
    record = {"protocol": PROTOCOL, "task_id": task["task_id"], "attempt": attempt,
              "session_id": session_id, "stages": rows,
              "status": result[0], "reason": result[1]}
    (attempt_dir / "attempt.json").write_text(json.dumps(record, indent=2) + "\n")
    return result


def run_task(task: dict, mode: str, harness: dict, treatment: dict,
             run_root: Path, launch_ceiling: float) -> tuple[str, str]:
    root = run_root / task["task_id"]
    attempts = sorted(root.glob("attempt-*")) if root.exists() else []
    if attempts:
        last = json.loads((attempts[-1] / "attempt.json").read_text())
        if last["status"] != "INFRA_INVALID":
            return last["status"], last["reason"]
    for number in range(len(attempts) + 1, 4):
        status, reason = run_attempt(
            task, number, mode, harness, treatment, run_root, launch_ceiling)
        if status == "INFRA_INVALID" and reason == "usage_limit":
            return status, reason
        if status != "INFRA_INVALID":
            return status, reason
    return "INFRA_INVALID", "three attempts exhausted"


def preflight(manifest_path: Path, manifest: dict) -> dict:
    if cli_version() != CLI_VERSION:
        raise RunnerError(f"Claude Code {cli_version()!r}; frozen version is {CLI_VERSION!r}")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RunnerError("tracked working tree is dirty")
    if not TREATMENT_FREEZE.exists() or sha256(TREATMENT_FREEZE) != manifest.get("treatment_freeze_sha256"):
        raise RunnerError("treatment freeze is missing or does not match run manifest")
    treatment = json.loads(TREATMENT_FREEZE.read_text())
    if treatment.get("status") != "TREATMENT_FROZEN":
        raise RunnerError("treatment is not frozen")
    first = manifest["tasks"][0]
    stages = ("a",) if manifest["mode"] == "heldout_a" else STAGES
    infrastructure = {"auth": auth_preflight(), "network": network_preflight(),
                      "mcp": [mcp_preflight(first, stage, treatment) for stage in stages]}
    return {"commit": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
            "manifest_sha256": sha256(manifest_path),
            "treatment_freeze_sha256": sha256(TREATMENT_FREEZE),
            "infrastructure_preflight": infrastructure}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    if args.dry_run:
        print(json.dumps({"mode": manifest["mode"], "tasks": [task["task_id"] for task in manifest["tasks"]],
                          "launch_ceiling_usd": manifest["launch_ceiling_usd"]}, indent=2))
        return
    if any(RUNS.joinpath(manifest["mode"], task["task_id"]).exists()
           for task in manifest["tasks"]):
        # Existing attempts are resumed by run_task; this check only prevents mixing another manifest.
        prior = RUNS / manifest["mode"] / "run-manifest.json"
        if not prior.exists() or sha256(prior) != sha256(args.manifest):
            raise SystemExit("existing run directory belongs to a different manifest")
    harness = preflight(args.manifest, manifest)
    run_root = RUNS / manifest["mode"]
    run_root.mkdir(parents=True, exist_ok=True)
    frozen_manifest = run_root / "run-manifest.json"
    if not frozen_manifest.exists():
        shutil.copyfile(args.manifest, frozen_manifest)
    treatment = json.loads(TREATMENT_FREEZE.read_text())
    for task in manifest["tasks"]:
        status, reason = run_task(task, manifest["mode"], harness, treatment, run_root,
                                  manifest["launch_ceiling_usd"])
        print(f"{status:16} {task['task_id']}: {reason}", flush=True)
        if status == "INFRA_INVALID" and reason == "usage_limit":
            print("STOP: external usage limit; resume with the same manifest later", flush=True)
            return
        if status == "INFRA_INVALID":
            print("STOP: unresolved infrastructure failure", flush=True)
            return
        if status in ("HARNESS_INVALID", "BUDGET_CENSORED"):
            print("STOP: protocol/infrastructure failure", flush=True)
            return


if __name__ == "__main__":
    main()
