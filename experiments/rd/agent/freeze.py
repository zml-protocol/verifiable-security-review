"""Write or verify the complete RD step-6 protocol freeze."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import tasks  # noqa: E402

FREEZE = HERE / "freeze.json"
PILOT_RESULT = ROOT / "runs" / "rd" / "agent" / "pilot" / "result.json"


class FreezeError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol_files() -> list[Path]:
    files = [HERE / name for name in (
        "PROTOCOL.md", "README.md", "manifest.yaml", "order.txt", "phases.py", "verifiability.py",
        "schema.py", "source.py", "session.py", "mcp_server.py", "tasks.py", "analysis.py",
        "graph.py", "reference.py", "run.py", "score.py", "pilot.py", "freeze.py",
        "prompt-a.md", "prompt-b.md", "prompt-c.md",
    )]
    files += [p for p in sorted((HERE / "pilot").rglob("*"))
              if p.is_file() and (p.suffix in (".py", ".go") or p.name == "go.mod")]
    files += [ROOT / "PREREGISTRATION.md", ROOT / "pyproject.toml", ROOT / "uv.lock",
              ROOT / "tests" / "test_rd_agent.py", ROOT / "tests" / "test_rd_protocol.py",
              ROOT / "results" / "rd-vocabulary.json",
              ROOT / "results" / "rd-candidate-pool.json", ROOT / "results" / "rd-agent-v1.json"]
    files += [ROOT / p for p in (
        "experiments/rd/truth/matcher.py", "experiments/rd/truth/resolver.py",
        "experiments/rd/truth/agreement.py", "experiments/rd/truth/vocabulary.py",
        "experiments/rd/truth/revision_map.py", "experiments/rd/truth/matcher-provenance.json",
        "experiments/rd/truth/truth-tooling-freeze.json",
        "experiments/agent_verify/validity.py",
        "experiments/hop_verify/verify.py", "experiments/provider_reach/reach.py",
        "experiments/hop_verify/relations.yaml", "experiments/hop_bridge/relations.yaml",
        "experiments/hop_chain/chain.py", "experiments/hop_chain/connector.py",
        "experiments/hop_chain/queries/go/SameObject.ql",
        "src/spike/anchors.py", "src/spike/gitrepo.py", "src/spike/hops.py",
        "src/spike/linemap.py", "src/spike/models.py", "src/spike/session.py",
    )]
    files += sorted((ROOT / "experiments" / "hop_verify" / "queries").rglob("*.ql*"))
    files += sorted((ROOT / "experiments" / "hop_bridge" / "queries").rglob("*.ql*"))
    seen = set()
    return [p for p in files if p.is_file() and not (str(p) in seen or seen.add(str(p)))]


def truth_files() -> list[Path]:
    fixtures = dict.fromkeys(tasks.task(tid)["fixture"] for tid in tasks.order())
    files = []
    for fixture in fixtures:
        base = ROOT / "experiments" / "rd" / "truth" / "fixtures" / fixture
        files += [base / "requirement-truth.yaml", base / "reference-evidence.yaml",
                  base / "reference-result.json"]
    files.append(ROOT / "experiments" / "rd" / "truth" / "negative-controls" /
                 "GO-2026-6237" / "result.yaml")
    return files


def analysis_entries() -> dict:
    out = {}
    for task_id in tasks.order():
        out[task_id] = {}
        t = tasks.task(task_id)
        for revision in ("revision_A", "revision_B"):
            path = ROOT / "runs" / "rd" / "agent" / "analysis" / task_id / revision / "analysis.json.gz"
            if not path.exists():
                raise FreezeError(f"missing analysis {path}")
            doc = json.loads(gzip.decompress(path.read_bytes()))
            if doc.get("status") != "ok" or doc.get("commit") != t["revisions"][revision]:
                raise FreezeError(f"analysis provenance mismatch: {task_id}/{revision}")
            out[task_id][revision] = {"sha256_gzip": sha256(path),
                                      "sha256_json": hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest(),
                                      "commit": doc["commit"], "tree": doc["tree"]}
    return out


def build() -> dict:
    if not PILOT_RESULT.exists():
        raise FreezeError("synthetic pilot result is missing")
    pilot = json.loads(PILOT_RESULT.read_text())
    if pilot.get("status") != "PASS":
        raise FreezeError(f"synthetic pilot did not pass: {pilot.get('problems')}")
    files = [*protocol_files(), *truth_files()]
    missing = [str(p) for p in files if not p.exists()]
    if missing:
        raise FreezeError(f"missing freeze inputs: {missing}")
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                            text=True, check=True).stdout.strip()
    return {"schema": "rd-agent-freeze/v2", "protocol": "rd-v2",
            "created_from_commit": commit,
            "prior_invalid_run": {"protocol": "rd-v1",
                                  "result": "results/rd-agent-v1.json",
                                  "result_sha256": sha256(ROOT / "results" / "rd-agent-v1.json"),
                                  "status": "HARNESS_INVALID",
                                  "reason": "sandbox DNS failure before any usable interaction"},
            "execution": {"model": "claude-sonnet-5", "effort": "high",
                          "claude_code_version": "2.1.280",
                          "phase_budget_usd": {"a": 3.0, "b": 3.0, "c": 1.0},
                          "cumulative_session_cap_usd": {"a": 3.0, "b": 6.0, "c": 7.0},
                          "phase_timeout_seconds": {"a": 1200, "b": 1800, "c": 600},
                          "launch_ceiling_usd": 42.0},
            "files": {str(p.relative_to(ROOT)): sha256(p) for p in files},
            "analysis": analysis_entries(),
            "pilot": {"result_sha256": sha256(PILOT_RESULT),
                      "synthetic_source": pilot.get("synthetic_source")}}


def write() -> None:
    doc = build()
    FREEZE.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {FREEZE.relative_to(ROOT)} with {len(doc['files'])} file hashes")


def verify() -> dict:
    if not FREEZE.exists():
        raise FreezeError(f"missing protocol freeze: {FREEZE}")
    frozen = json.loads(FREEZE.read_text())
    problems = []
    for name, expected in frozen.get("files", {}).items():
        path = ROOT / name
        if not path.exists() or sha256(path) != expected:
            problems.append(f"file drift: {name}")
    try:
        current = analysis_entries()
        if current != frozen.get("analysis"):
            problems.append("analysis drift")
    except FreezeError as e:
        problems.append(str(e))
    if not PILOT_RESULT.exists() or sha256(PILOT_RESULT) != (frozen.get("pilot") or {}).get("result_sha256"):
        problems.append("pilot result drift")
    if problems:
        raise FreezeError("; ".join(problems))
    return frozen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("write", "verify"))
    args = ap.parse_args()
    write() if args.command == "write" else print(json.dumps({
        "status": "OK", "protocol": verify()["protocol"]}, indent=2))


if __name__ == "__main__":
    main()
