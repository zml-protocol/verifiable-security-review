"""Run one RD adjudication session in an isolated local OpenCode (PREREGISTRATION.md §15.1).

    uv run python experiments/rd/boundary/judge_opencode.py --round 2 --judge b --model deepseek/deepseek-flash

The second model family for a round (judge_codex.py runs the OpenAI one). Isolation, as for Codex:
- fresh HOME and XDG config/data/cache/state directories: none of the user's OpenCode config, MCP
  servers, plugins, rules, sessions or database; Claude Code files are not read;
- a minimal config of our own: every tool off and every permission denied; --standalone (a private
  server, not the shared background service); an empty working directory outside any repository;
- the public model catalog (models.json) is copied in so the model resolves; OpenCode 2 keeps
  credentials in its database, so the provider key is read from the user's OpenCode auth.json and
  passed to this one subprocess as the provider's environment variable, never written anywhere;
- the prompt (sheet and template inline) is judge_codex.prompt_text, identical for both judges.
Validity is checked mechanically: the event log must hold only text, reasoning and step events;
any tool part or error makes the run INVALID. If the reply's YAML does not parse, the same session
is asked once to fix the format only. The model exposes no reasoning-effort setting: provider default.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import decide as D
import judge_codex as J

CONFIG = {"$schema": "https://opencode.ai/config.json", "autoupdate": False, "share": "disabled",
          "tools": {"*": False}, "permission": {"*": "deny"}}
TEXT_PARTS = {"text", "reasoning", "step-start", "step-finish"}
KEY_ENV = {"deepseek": "DEEPSEEK_API_KEY"}


def opencode(args: list[str], root: Path, key_env: dict, timeout: int) -> tuple[int, str, str]:
    env = {**os.environ, "HOME": str(root / "home"), "XDG_CONFIG_HOME": str(root / "config"),
           "XDG_DATA_HOME": str(root / "data"), "XDG_CACHE_HOME": str(root / "cache"),
           "XDG_STATE_HOME": str(root / "state"), "OPENCODE_DISABLE_CLAUDE_CODE": "1",
           "OPENCODE_DISABLE_AUTOUPDATE": "1", "OPENCODE_DISABLE_DEFAULT_PLUGINS": "1", **key_env}
    p = subprocess.run(["opencode", "run", "--standalone", "--format", "json", *args],
                       cwd=root / "work", env=env, stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=timeout, check=False)
    return p.returncode, p.stdout, p.stderr


def events_summary(stdout: str) -> dict:
    parts, errors, session, text = [], [], None, []
    for line in stdout.splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        session = session or e.get("sessionID")
        if e.get("type") == "error" or e.get("error"):
            errors.append(e)
        part = e.get("part") or {}
        if part:
            parts.append(part.get("type"))
            if part.get("type") == "text":
                text.append(part.get("text") or "")
    return {"session": session, "errors": errors, "parts": parts, "reply": "".join(text),
            "tool_parts": sorted({p for p in parts if p not in TEXT_PARTS})}


def setup(root: Path, provider: str) -> dict:
    for d in ("home", "config/opencode", "data/opencode", "cache/opencode", "state", "work"):
        (root / d).mkdir(parents=True, mode=0o700)
    (root / "config/opencode/opencode.json").write_text(json.dumps(CONFIG, indent=2))
    shutil.copyfile(Path.home() / ".cache/opencode/models.json", root / "cache/opencode/models.json")
    auth = json.loads((Path.home() / ".local/share/opencode/auth.json").read_text())
    return {KEY_ENV[provider]: auth[provider]["key"]}


def run(n: int, judge: str, model: str, timeout: int) -> dict:
    manifest = json.loads((J.RESULTS / f"rd-boundary-r{n}-manifest.json").read_text())
    out_dir = J.RUNS / f"r{n}-{judge}"
    target = J.RESULTS / f"rd-boundary-r{n}-judge-{judge}.yaml"
    if target.exists():
        sys.exit(f"{target.name} exists; a judge runs once (move it aside to rerun an INVALID run)")
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    provider = model.split("/", 1)[0]
    root = Path(tempfile.mkdtemp(prefix=f"rd-judge-{judge}-"))
    prompt = J.prompt_text(n)
    started = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    try:
        key_env = setup(root, provider)
        code, stdout, stderr = opencode(["-m", model, prompt], root, key_env, timeout)
        (out_dir / "events.jsonl").write_text(stdout)
        (out_dir / "stderr.txt").write_text(stderr)
        summary = events_summary(stdout)
        (out_dir / "reply.txt").write_text(summary["reply"])
        block = J.yaml_block(summary["reply"])
        problems = J.parses(block, manifest, root)
        fix = None
        if problems and summary["session"] and not summary["tool_parts"]:
            code2, stdout2, stderr2 = opencode(["-m", model, "--session", summary["session"], J.FIX_FORMAT],
                                               root, key_env, timeout)
            (out_dir / "events-fix.jsonl").write_text(stdout2)
            (out_dir / "stderr-fix.txt").write_text(stderr2)
            summary2 = events_summary(stdout2)
            (out_dir / "reply-fixed.txt").write_text(summary2["reply"])
            fix = {"exit": code2, "problems_before": problems, "tool_parts": summary2["tool_parts"]}
            summary["tool_parts"] = sorted(set(summary["tool_parts"]) | set(summary2["tool_parts"]))
            summary["errors"] += summary2["errors"]
            block = J.yaml_block(summary2["reply"])
            problems = J.parses(block, manifest, root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    version = subprocess.run(["opencode", "--version"], capture_output=True, text=True, check=False).stdout.strip()
    valid = code == 0 and not summary["tool_parts"] and not summary["errors"] and not problems
    record = {
        "round": n, "judge": judge, "model": model, "reasoning_effort": "provider default (not exposed)",
        "opencode_cli": version, "started_utc": started, "exit": code, "session": summary["session"],
        "event_parts": summary["parts"], "tool_parts": summary["tool_parts"], "errors": summary["errors"],
        "format_fix": fix, "problems": problems, "valid": valid,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "sheet_sha256": manifest["sheet_sha256"],
        "isolation": {"home_and_xdg_dirs": "fresh temporary directories (deleted)",
                      "config": CONFIG, "server": "--standalone",
                      "workdir": "empty temporary directory outside any repository (deleted)",
                      "credential": f"{KEY_ENV[provider]} passed via the subprocess environment, read "
                                    "from the user's OpenCode auth.json, not written anywhere",
                      "catalog": "copy of the public models.json"},
    }
    if valid:
        target.write_text(block)
    (J.RESULTS / f"rd-boundary-r{n}-judge-{judge}.provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--judge", choices=D.JUDGES, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--timeout", type=int, default=3600)
    a = ap.parse_args()
    r = run(a.round, a.judge, a.model, a.timeout)
    print(json.dumps({k: r[k] for k in ("judge", "model", "valid", "exit", "tool_parts", "problems")}, indent=1))
    sys.exit(0 if r["valid"] else 1)


if __name__ == "__main__":
    main()
