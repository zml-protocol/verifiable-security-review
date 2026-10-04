"""Manual-check kit for the RD selection step (fieldwork tool, not part of §15).

    uv run python experiments/fieldwork/rd_manual_kit.py <candidate-id> [...] [--build-go|--build-py]

For each candidate it prepares, under runs/rd/precheck/<id>/:

- trees/parent and trees/fix: detached worktrees from the cached bare repo (offline),
- env.json: toolchain paths and versions, worktree paths, per-side diagnostic builds,
- decision.md: a template pre-filled with the mechanical facts from rd_precheck, ready for the
  manual checker to add route, files read, commands, parent/fix results, elapsed time and verdict.

It never reads the advisory text, never runs a test or probe, never writes a verdict, and never
touches results/, the selection log or selection.py. Builds are diagnostic: a failure here is a
fact for the checker, not a BUILD_UNAVAILABLE verdict. Go builds use ``-mod=readonly``; Python
gets one editable environment per side so neither tree leaks into the other.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rd_precheck import OUT as PRECHECK_OUT  # noqa: E402
from rd_precheck import candidate, git, one as precheck_one  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
GO_BIN = ROOT / ".cache" / "toolchains" / "go1.26.8" / "bin"


def run(cmd: list[str], cwd: Path, timeout: int, env: dict | None = None) -> dict:
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout,
                              env=env, check=False)
        lines = (proc.stdout + proc.stderr).strip().splitlines()
        return {"cmd": " ".join(cmd), "code": proc.returncode,
                "seconds": round(time.time() - started, 1), "tail": lines[-6:]}
    except subprocess.TimeoutExpired:
        return {"cmd": " ".join(cmd), "code": "timeout", "seconds": timeout, "tail": []}
    except FileNotFoundError as exc:
        return {"cmd": " ".join(cmd), "code": "missing", "seconds": 0, "tail": [str(exc)]}


def make_worktree(repo: Path, sha: str, dest: Path) -> str:
    if dest.exists():
        return "exists"
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(dest), sha],
                          capture_output=True, text=True, check=False)
    return "ok" if proc.returncode == 0 else f"fail: {proc.stderr.strip()[:200]}"


def find_go_module(tree: Path) -> Path | None:
    if (tree / "go.mod").exists():
        return tree
    for depth in ("*/go.mod", "*/*/go.mod"):
        matches = sorted(tree.glob(depth))
        if matches:
            return matches[0].parent
    return None


def go_toolchain() -> dict:
    env = dict(os.environ, PATH=f"{GO_BIN}:{os.environ.get('PATH', '')}")
    version = run(["go", "version"], ROOT, 60, env)
    settings = run(["go", "env", "GOMODCACHE", "GOCACHE", "GOPROXY", "GOTOOLCHAIN"], ROOT, 60, env)
    return {"version": version.get("tail", []), "env": settings.get("tail", [])}


def build_go(tree: Path) -> list[dict]:
    # -mod=readonly: dependency resolution must not mutate go.mod/go.sum during evidence-gathering.
    env = dict(os.environ, PATH=f"{GO_BIN}:{os.environ.get('PATH', '')}", GOFLAGS="-mod=readonly")
    module = find_go_module(tree)
    if module is None:
        return [{"cmd": "go build ./...", "code": "no go.mod found", "seconds": 0, "tail": []}]
    steps = [run(["go", "build", "./..."], module, 1500, env)]
    steps[0]["module"] = str(module.relative_to(tree)) or "."
    return steps


def project_distribution(tree: Path) -> str | None:
    try:
        import tomllib

        doc = tomllib.loads((tree / "pyproject.toml").read_text())
        name = (doc.get("project") or {}).get("name")
        return str(name) if name else None
    except Exception:
        return None


def build_py(tree: Path, out: Path, side: str) -> list[dict]:
    """Symmetric per-side environment: each tree gets its own editable install, so neither side
    silently leaks into the other's imports."""
    venv = out / f"venv-{side}"
    py = venv / "bin" / "python"
    steps: list[dict] = []
    if not py.exists():
        if venv.exists():
            shutil.rmtree(venv, ignore_errors=True)
        # --no-project: some repos pin a uv required-version; do not let it block the environment.
        steps.append(run(["uv", "venv", "--no-project", str(venv)], Path("/tmp/opencode"), 300))
    if py.exists():
        # neutral cwd so uv pip does not try to read the pinned project metadata for discovery
        steps.append(run(["uv", "pip", "install", "--python", str(py), "-e", str(tree)],
                         Path("/tmp/opencode"), 1800))
        steps.append(run([str(py), "--version"], Path("/tmp/opencode"), 60))
        name = project_distribution(tree)
        if name:
            smoke = "import importlib.metadata as m; print(m.version(%r))" % name
            steps.append(run([str(py), "-c", smoke], Path("/tmp/opencode"), 180))
        steps.append(run(["uv", "pip", "check", "--python", str(py)], Path("/tmp/opencode"), 180))
    return steps


def kit(pid: str, build: str | None) -> None:
    cand = candidate(pid)  # gated: selection.checked() runs before the pool is read
    # regenerate the mechanical facts through the gated precheck; never trust a historical file
    facts = precheck_one(pid)
    output = PRECHECK_OUT / pid
    output.mkdir(parents=True, exist_ok=True)
    repo = ROOT / ".cache" / "rd" / "candidates" / pid
    fix = cand["fix_commit"]
    parent = git(repo, "rev-parse", f"{fix}^").strip()
    lang = next(iter(cand["listed_in"].values()))
    if lang == "python":
        stale = output / "venv"  # pre-symmetric layout; remove so it cannot be mistaken for a side env
        if stale.exists():
            shutil.rmtree(stale, ignore_errors=True)

    trees = output / "trees"
    wt = {"parent": make_worktree(repo, parent, trees / "parent"),
          "fix": make_worktree(repo, fix, trees / "fix")}

    builds: dict[str, list[dict]] = {}
    if build == "go" or (build is None and lang == "go"):
        builds = {"parent": build_go(trees / "parent"), "fix": build_go(trees / "fix")}
    elif build == "py" or (build is None and lang == "python"):
        builds = {"parent": build_py(trees / "parent", output, "parent"),
                  "fix": build_py(trees / "fix", output, "fix")}

    env = {
        "id": pid, "repo": cand["repo"], "language": lang, "fix_commit": fix, "parent": parent,
        "worktrees": {"parent": str(trees / "parent"), "fix": str(trees / "fix")},
        "toolchain": (go_toolchain() if lang == "go" else
                      {"uv": run(["uv", "--version"], ROOT, 60).get("tail", [])}),
        "builds": builds,
        "note": "diagnostic only; the checker decides and records the verdict with `decide`",
    }
    (output / "env.json").write_text(json.dumps(env, indent=1) + "\n")

    f = facts.get("facts", {})
    tests = [x for x in facts.get("files", []) if x.get("test")]
    lines = [
        f"# Manual admissibility check: {pid}", "",
        "Prepared by `rd_manual_kit.py` (mechanical facts only). The checker fills every blank",
        "and runs the frozen `decide` command. Review boundary and routes: see",
        "`experiments/rd/selection-handoff.md`.", "",
        "## Mechanical facts", "",
        f"- repository: {cand['repo']}",
        f"- fix commit: `{fix}` / parent `{parent}`",
        f"- changed files: {f.get('file_count', '?')} "
        f"({f.get('test_file_count', '?')} test, non-test non-dependency lines "
        f"{f.get('non_test_non_dep_lines', '?')})",
        f"- test files that mention advisory identifiers: "
        f"{len(f.get('test_files_with_advisory_identifiers', {}))}",
        "",
        "| path | status | + | - | test |",
        "|---|---|---:|---:|---|",
    ]
    for x in facts.get("files", []):
        lines.append(f"| `{x['path']}` | {x['status']} | {x['added']} | {x['deleted']} | "
                     f"{'yes' if x['test'] else ''} |")
    lines += ["", "## Prepared environment", "",
              f"- parent worktree: `{env['worktrees']['parent']}`",
              f"- fix worktree: `{env['worktrees']['fix']}`"]
    for side, steps in builds.items():
        for s in steps:
            extra = f" (module `{s['module']}`)" if s.get("module") else ""
            lines.append(f"- build[{side}]: `{s['cmd']}`{extra} -> exit {s['code']} ({s['seconds']}s)")
    if lang == "python":
        for side in ("parent", "fix"):
            py = output / f"venv-{side}" / "bin" / "python"
            if py.exists():
                lines.append(f"- run the {side} tree: `{py} ...` (editable install of that tree)")
    if lang == "go" and builds.get("fix") and builds["fix"][0].get("module"):
        lines += [f"- build/test inside `{env['worktrees']['fix']}/{builds['fix'][0]['module']}`"]
    lines += [
        "", "## Checker fills in", "",
        "- route (TEST / POC / PROBE) and why the earlier routes do not apply: ______",
        "- exact set of files read (must stay inside the review boundary): ______",
        "- exact commands run: ______",
        "- parent result: ______",
        "- fix result: ______",
        "- elapsed probe time (PROBE only): ______",
        "- review boundary reached (yes/no): ______",
        "- verdict (frozen enumeration) and one-line evidence: ______",
        "",
        "Record the verdict with:",
        f"`uv run python experiments/rd/selection.py decide --id {pid} --verdict <VERDICT> "
        "[--route <ROUTE>] --evidence \"<one line>\"`",
        "",
    ]
    (output / "decision.md").write_text("\n".join(lines))
    print(f"{pid}: worktrees {wt}, builds "
          f"{ {k: [s['code'] for s in v] for k, v in builds.items()} }")
    print(f"  -> runs/rd/precheck/{pid}/decision.md")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    build = "go" if "--build-go" in sys.argv else "py" if "--build-py" in sys.argv else None
    if not args:
        sys.exit(__doc__)
    for pid in args:
        kit(pid, build)


if __name__ == "__main__":
    main()
