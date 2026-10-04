"""Run one RD adjudication session in an isolated local Codex CLI (PREREGISTRATION.md §15.1).

    uv run python experiments/rd/boundary/judge_codex.py --round 1 --judge a --model gpt-6-astra
    uv run python experiments/rd/boundary/judge_codex.py --round 1 --judge b --model gpt-6.1-sol

Isolation (the adjudicator must not see this project, its labels or any earlier conversation):
- a fresh CODEX_HOME holding only a link to the login: no config, hooks, plugins, memories,
  history, skills or AGENTS.md;
- an empty working directory outside any repository, read-only sandbox;
- every tool feature that can be switched off is off (FEATURES_OFF), web search disabled;
- the sheet and template are given inline in the prompt (the operator prompt of
  rd-boundary-r<N>-instructions.md, with "attached" replaced by "below"), with the instruction to
  use no tool.
Some built-in tools cannot be switched off, so validity is checked mechanically: the event log
must contain only the reply and reasoning. Any tool call makes the run INVALID (rerun it).
If the reply's YAML does not parse, the same session is asked once to fix the format only.

Writes results/rd-boundary-r<N>-judge-<j>.yaml (the reply's YAML block, verbatim) and
results/rd-boundary-r<N>-judge-<j>.provenance.json; the event logs and the session transcript go
to runs/rd/adjudication/r<N>-<j>/. The temporary CODEX_HOME is deleted afterwards.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESULTS = ROOT / "results"
RUNS = ROOT / "runs" / "rd" / "adjudication"
sys.path.insert(0, str(HERE))

import decide as D

FEATURES_OFF = [
    "shell_tool", "unified_exec", "unified_exec_tty", "code_mode_host", "multi_agent", "view_image",
    "sleep_tool", "apps", "plugins", "remote_plugin", "plugin_sharing", "hooks", "memories",
    "browser_use", "browser_use_external", "browser_use_full_cdp_access", "computer_use",
    "image_generation", "goals", "skill_search", "skill_mcp_dependency_install", "tool_suggest",
    "in_app_browser", "in_app_local_automation", "worktrees", "workspace_dependencies",
    "realtime_conversation", "shell_snapshot",
]
TEXT_ITEMS = {"agent_message", "reasoning"}
FIX_FORMAT = ("Your reply did not parse as YAML in the form of the template. Reply again with only "
              "the YAML, fixing the format only: do not change any label or note.")


def prompt_text(n: int) -> str:
    instructions = (RESULTS / f"rd-boundary-r{n}-instructions.md").read_text()
    body = instructions.split("## Prompt", 1)[1].strip()
    body = " ".join(line.lstrip("> ").strip() for line in body.splitlines()).strip()
    body = body.replace("The attached sheet", "The sheet below").replace("the attached template",
                                                                          "the template below")
    sheet = (RESULTS / f"rd-boundary-r{n}-sheet.md").read_text()
    template = (RESULTS / f"rd-boundary-r{n}-labels.template.yaml").read_text()
    return (f"{body}\n\nDo not use any tool, command or file: everything you need is in this "
            f"message. Reply with the YAML only.\n\n===== SHEET =====\n{sheet}\n"
            f"===== TEMPLATE =====\n{template}")


def codex(args: list[str], stdin: str, home: Path, work: Path, timeout: int) -> tuple[int, str, str]:
    env = dict(os.environ)
    env["CODEX_HOME"] = str(home)
    p = subprocess.run(["codex", "exec", *args], input=stdin, capture_output=True, text=True,
                       cwd=work, env=env, timeout=timeout, check=False)
    return p.returncode, p.stdout, p.stderr


def common_flags(model: str, effort: str, work: Path, resume: bool = False) -> list[str]:
    """`exec resume` takes no -C/--sandbox: there the cwd comes from the process and the sandbox
    from the config override."""
    flags = ["--skip-git-repo-check", "-m", model, "-c", f'model_reasoning_effort="{effort}"',
             "-c", 'web_search="disabled"', "--json"]
    flags += ["-c", 'sandbox_mode="read-only"'] if resume else ["-C", str(work), "--sandbox", "read-only"]
    for f in FEATURES_OFF:
        flags += ["--disable", f]
    return flags


def events_summary(stdout: str) -> dict:
    """Items inside the turn other than the reply and reasoning are tool use. An `error` item
    before the turn starts is the CLI's startup notice (with code_mode_host off: "Code Mode is
    unavailable ..."), not the model's doing: it is recorded, not counted as a tool."""
    items, notices, thread, usage, errors, in_turn = [], [], None, None, [], False
    for line in stdout.splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = e.get("type")
        if t == "thread.started":
            thread = e.get("thread_id")
        elif t == "turn.started":
            in_turn = True
        elif t == "turn.completed":
            usage = e.get("usage")
        elif t in ("error", "turn.failed"):
            errors.append(e)
        elif t in ("item.started", "item.completed"):
            item = e.get("item") or {}
            if not in_turn and item.get("type") == "error":
                notices.append(item.get("message"))
            else:
                items.append(item.get("type"))
    return {"thread_id": thread, "usage": usage, "errors": errors, "items": items,
            "startup_notices": notices, "tool_items": sorted({i for i in items if i not in TEXT_ITEMS})}


def yaml_block(text: str) -> str:
    m = re.search(r"```(?:yaml|yml)?\s*\n(.*?)```", text, re.DOTALL)
    return (m.group(1) if m else text).strip() + "\n"


def parses(block: str, manifest: dict, tmp: Path) -> list[str]:
    f = tmp / "probe.yaml"
    f.write_text(block)
    try:
        return D.load_judge(f, manifest)[1]
    except yaml.YAMLError as e:
        return [f"yaml: {e}"]


def run(n: int, judge: str, model: str, effort: str, timeout: int) -> dict:
    manifest = json.loads((RESULTS / f"rd-boundary-r{n}-manifest.json").read_text())
    out_dir = RUNS / f"r{n}-{judge}"
    target = RESULTS / f"rd-boundary-r{n}-judge-{judge}.yaml"
    if target.exists():
        sys.exit(f"{target.name} exists; a judge runs once (move it aside to rerun an INVALID run)")
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    tmp = Path(tempfile.mkdtemp(prefix=f"rd-judge-{judge}-"))
    home, work = tmp / "home", tmp / "work"
    home.mkdir(mode=0o700)
    work.mkdir()
    (home / "auth.json").symlink_to(Path.home() / ".codex" / "auth.json")
    prompt = prompt_text(n)
    started = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    try:
        code, stdout, stderr = codex([*common_flags(model, effort, work), "-o", str(out_dir / "reply.txt")],
                                     prompt, home, work, timeout)
        (out_dir / "events.jsonl").write_text(stdout)
        (out_dir / "stderr.txt").write_text(stderr)
        summary = events_summary(stdout)
        reply = (out_dir / "reply.txt").read_text() if (out_dir / "reply.txt").exists() else ""
        block = yaml_block(reply)
        problems = parses(block, manifest, tmp)
        fix = None
        if problems and summary["thread_id"] and not summary["tool_items"]:
            code2, stdout2, stderr2 = codex(
                ["resume", summary["thread_id"], *common_flags(model, effort, work, resume=True),
                 "-o", str(out_dir / "reply-fixed.txt")], FIX_FORMAT, home, work, timeout)
            (out_dir / "events-fix.jsonl").write_text(stdout2)
            (out_dir / "stderr-fix.txt").write_text(stderr2)
            summary2 = events_summary(stdout2)
            reply2 = (out_dir / "reply-fixed.txt").read_text() if (out_dir / "reply-fixed.txt").exists() else ""
            fix = {"exit": code2, "problems_before": problems, "tool_items": summary2["tool_items"]}
            summary["tool_items"] = sorted(set(summary["tool_items"]) | set(summary2["tool_items"]))
            block = yaml_block(reply2)
            problems = parses(block, manifest, tmp)
        for f in (home / "sessions").rglob("*.jsonl"):
            shutil.copyfile(f, out_dir / f"session.{f.name}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    version = subprocess.run(["codex", "--version"], capture_output=True, text=True, check=False).stdout.strip()
    valid = code == 0 and not summary["tool_items"] and not summary["errors"] and not problems
    record = {
        "round": n, "judge": judge, "model": model, "reasoning_effort": effort, "codex_cli": version,
        "started_utc": started, "exit": code, "thread_id": summary["thread_id"], "usage": summary["usage"],
        "event_items": summary["items"], "startup_notices": summary["startup_notices"],
        "tool_items": summary["tool_items"], "errors": summary["errors"],
        "format_fix": fix, "problems": problems, "valid": valid,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "sheet_sha256": manifest["sheet_sha256"],
        "isolation": {"codex_home": "fresh temporary directory with only a link to auth.json (deleted)",
                      "workdir": "empty temporary directory outside any repository (deleted)",
                      "sandbox": "read-only", "features_off": FEATURES_OFF, "web_search": "disabled"},
    }
    if valid:
        target.write_text(block)
    (RESULTS / f"rd-boundary-r{n}-judge-{judge}.provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def finalize(n: int, judge: str) -> dict:
    """Re-apply the validity rule to a finished run's saved event log and reply (no new session)."""
    manifest = json.loads((RESULTS / f"rd-boundary-r{n}-manifest.json").read_text())
    out_dir = RUNS / f"r{n}-{judge}"
    prov_path = RESULTS / f"rd-boundary-r{n}-judge-{judge}.provenance.json"
    target = RESULTS / f"rd-boundary-r{n}-judge-{judge}.yaml"
    if target.exists():
        sys.exit(f"{target.name} exists")
    record = json.loads(prov_path.read_text())
    if record.get("format_fix"):
        sys.exit("a format-fixed run is not re-evaluated here")
    summary = events_summary((out_dir / "events.jsonl").read_text())
    block = yaml_block((out_dir / "reply.txt").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        problems = parses(block, manifest, Path(tmp))
    valid = record["exit"] == 0 and not summary["tool_items"] and not summary["errors"] and not problems
    record |= {"event_items": summary["items"], "startup_notices": summary["startup_notices"],
               "tool_items": summary["tool_items"], "errors": summary["errors"], "problems": problems,
               "valid": valid, "reevaluated": "startup notices before the turn are not tool use"}
    if valid:
        target.write_text(block)
    prov_path.write_text(json.dumps(record, indent=2) + "\n")
    return record


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--judge", choices=D.JUDGES, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--finalize", action="store_true", help="re-evaluate a finished run's saved logs")
    a = ap.parse_args()
    r = finalize(a.round, a.judge) if a.finalize else run(a.round, a.judge, a.model, a.effort, a.timeout)
    print(json.dumps({k: r[k] for k in ("judge", "model", "valid", "exit", "tool_items", "problems", "usage")},
                     indent=1))
    sys.exit(0 if r["valid"] else 1)


if __name__ == "__main__":
    main()
