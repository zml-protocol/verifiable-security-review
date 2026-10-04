"""Run the fixture-free, no-model RD v3 plumbing pilot.

The pilot exercises the exact session/checkpoint/C split and accounting helpers
without opening held-out data or making a paid model call.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[3]
for directory in (HERE, PARENT):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from spike.session import ToolInputError  # noqa: E402

import rdv3_checkpoint as checkpoint  # noqa: E402
import rdv3_contract as contract  # noqa: E402
import rdv3_runner as runner  # noqa: E402
from rdv3_session import V3Config, V3Session  # noqa: E402

RUN = ROOT / "runs" / "rd" / "agent" / "rd-v3" / "development" / "pilot"
RESULT = RUN / "result.json"
SOURCE_A = """package pilot

func sink(string) {}
func safe(string) bool { return true }
func Evaluate(input string) {
\tvalue := input
\tsink(value)
}
"""
SOURCE_B = """package pilot

func sink(string) {}
func safe(string) bool { return true }
func Evaluate(input string) {
\tvalue := input
\tif safe(value) {
\t\tsink(value)
\t}
}
"""


class PilotFailure(RuntimeError):
    pass


def _git(repo: Path, *args: str, env: dict | None = None) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                            check=False, env=env)
    if result.returncode:
        raise PilotFailure(result.stderr.strip())
    return result.stdout.strip()


def _write_revision(repo: Path, source: str) -> None:
    (repo / "p.go").write_text(source)
    (repo / "go.mod").write_text("module example.invalid/rd-v3-pilot\n\ngo 1.26\n")


def build_repo() -> tuple[Path, str, str]:
    repo = RUN / "repo"
    if repo.exists():
        shutil.rmtree(repo)
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _git(repo, "config", "user.name", "RD V3 Pilot")
    _git(repo, "config", "user.email", "rd-v3-pilot@example.invalid")
    env = {**os.environ, "GIT_AUTHOR_DATE": "2026-10-03T00:00:00Z",
           "GIT_COMMITTER_DATE": "2026-10-03T00:00:00Z"}
    _write_revision(repo, SOURCE_A)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "pilot revision A", env=env)
    first = _git(repo, "rev-parse", "HEAD")
    _write_revision(repo, SOURCE_B)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "pilot revision B", env=env)
    second = _git(repo, "rev-parse", "HEAD")
    return repo, first, second


def _anchor(line: int, expression: str) -> dict:
    return {"file": "p.go", "start_line": line, "end_line": line, "expression": expression}


def requirements() -> dict:
    return {
        "entry": {revision: {"state": "present", "anchor": _anchor(6, "value := input")}
                  for revision in contract.REVISIONS},
        "behavior": {
            "revision_A": {"state": "present", "anchor": _anchor(7, "sink(value)")},
            "revision_B": {"state": "present", "anchor": _anchor(7, "if safe(value) {")},
        },
        "required_qualifiers": [], "rationale": "pilot-only schema exercise",
    }


def analyses(first: str, second: str) -> dict[str, str]:
    out = {}
    for revision, commit in (("revision_A", first), ("revision_B", second)):
        behavior_col = 2
        doc = {
            "status": "ok", "commit": commit, "tree": f"pilot-{revision}",
            "shapes": [["file", "p.go", 1, 1, 10], ["parameter", "p.go", 5, 15, 5],
                       ["definition", "p.go", 6, 2, 6],
                       ["definition", "p.go", 7, behavior_col, 7]],
            "rows": {"def_use": [["p.go", 5, 15, "p.go", 6, 2],
                                   ["p.go", 6, 2, "p.go", 7, behavior_col]]},
            "same_object_rows": [],
        }
        path = RUN / "analysis" / f"{revision}.json.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(json.dumps(doc, sort_keys=True).encode(), mtime=0))
        out[revision] = str(path)
    return out


def config(repo: Path, first: str, second: str, phase: str, *, analysis: dict[str, str],
           c_stage: str | None = None, out_name: str | None = None) -> V3Config:
    return V3Config(
        session_id=f"rd-v3-pilot/{phase}/{c_stage or 'main'}", task_id="rd-v3-pilot",
        phase=phase, c_stage=c_stage, language="go",
        claim={"package": "example.invalid/rd-v3-pilot",
               "effect_claim": "attacker input may reach the pilot sink without its safety decision"},
        repo=str(repo), revisions={"revision_A": first, "revision_B": second},
        out_dir=str(RUN / (out_name or f"stage-{phase}")), artifact_dir=str(RUN / "artifacts"),
        analysis=analysis if phase == "b" else {},
        provider_sha256="a" * 64 if phase == "b" else "",
        relation_table_sha256="b" * 64 if phase == "b" else "",
    )


def run() -> dict:
    if RUN.exists():
        shutil.rmtree(RUN)
    RUN.mkdir(parents=True)
    repo, first, second = build_repo()
    analysis = analyses(first, second)
    checks = {}

    a_session = V3Session(config(repo, first, second, "a", analysis=analysis))
    checks["a_surface"] = sorted(a_session._tools)
    a_session.call("submit_requirements", requirements=requirements())

    b_session = V3Session(config(repo, first, second, "b", analysis=analysis))
    checks["b_surface"] = sorted(b_session._tools)
    verified = {"revision": "revision_A", "relation": "def_use",
                "from": _anchor(5, "input"), "to": _anchor(6, "value := input")}
    if b_session.call("check_hop", hop=verified) != {"feedback": "confirmed"}:
        raise PilotFailure("known pilot edge did not verify")
    unverified = {**verified, "from": _anchor(6, "value := input")}
    if b_session.call("check_hop", hop=unverified) != {"feedback": "not confirmed"}:
        raise PilotFailure("pilot near miss was not rejected")
    try:
        b_session.call("check_hop", hop={**verified, "to": _anchor(8, "}")})
        raise PilotFailure("structurally invalid hop was accepted")
    except ToolInputError:
        pass
    artifacts = RUN / "artifacts"
    partial = checkpoint.materialize(
        artifacts / "b-checkpoints", artifacts / "partial-checkpoint.json")
    terminal = checkpoint.materialize_terminal_b(artifacts)
    checks["checkpoint"] = {"events": partial["event_count"],
                            "last_successful_event": partial["last_successful_event"],
                            "terminal_status": terminal["status"]}

    try:
        V3Session(config(repo, first, second, "c", analysis=analysis, c_stage="c2",
                         out_name="stage-c2-too-early"))
        raise PilotFailure("C2 opened before C1")
    except ToolInputError:
        checks["c2_before_c1_rejected"] = True
    c1_session = V3Session(config(repo, first, second, "c", analysis=analysis, c_stage="c1"))
    checks["c1_surface"] = sorted(c1_session._tools)
    c1_session.call("submit_effect_attribution", conclusion={
        "revision_A": "SUPPORTED", "revision_B": "NOT_SUPPORTED"})
    c2_session = V3Session(config(repo, first, second, "c", analysis=analysis, c_stage="c2"))
    checks["c2_surface"] = sorted(c2_session._tools)
    c2_session.call("submit_cwe_taxonomy", taxonomy={"result": "NO_CONFIDENT_CWE"})

    tampered = RUN / "tampered-checkpoints"
    shutil.copytree(artifacts / "b-checkpoints", tampered)
    event_path = tampered / "events" / "000001.json"
    event = json.loads(event_path.read_text())
    event["resolution"]["state"] = "UNVERIFIED"
    event_path.write_text(json.dumps(event))
    try:
        checkpoint.load_and_verify_events(tampered)
    except Exception:
        checks["tampered_checkpoint_rejected"] = True
    else:
        raise PilotFailure("tampered checkpoint was accepted")

    isolated = runner.isolated_workdir()
    try:
        checks["isolated_workdir"] = not isolated.resolve().is_relative_to(ROOT)
    finally:
        shutil.rmtree(isolated)

    fake_runs = RUN / "accounting"
    attempt = fake_runs / "task" / "attempt-1"
    for stage, cost in (("a", 0.2), ("b", 0.5), ("c1", 0.7), ("c2", 0.8)):
        directory = attempt / f"stage-{stage}"
        directory.mkdir(parents=True)
        (directory / "agent.jsonl").write_text(json.dumps(
            {"type": "result", "total_cost_usd": cost}) + "\n")
    checks["cumulative_accounting"] = runner.observed_spend(fake_runs) == 0.8

    bad_c1 = json.loads((artifacts / "c1.json").read_text())
    bad_c1["conclusion"]["revision_A"] = "NOT_SUPPORTED"
    try:
        contract.verify_seal(bad_c1)
    except Exception:
        checks["tampered_c1_rejected"] = True
    else:
        raise PilotFailure("tampered C1 seal was accepted")

    expected_surfaces = {
        "a_surface": sorted(runner.PHASE_TOOLS["a"]),
        "b_surface": sorted(runner.PHASE_TOOLS["b"]),
        "c1_surface": sorted(runner.PHASE_TOOLS["c1"]),
        "c2_surface": sorted(runner.PHASE_TOOLS["c2"]),
    }
    problems = [f"{name} surface drift" for name, expected in expected_surfaces.items()
                if checks.get(name) != expected]
    problems += [name for name in ("c2_before_c1_rejected", "tampered_checkpoint_rejected",
                                   "isolated_workdir", "cumulative_accounting",
                                   "tampered_c1_rejected") if checks.get(name) is not True]
    result = {
        "schema": "rd-v3-offline-pilot-result/v1", "status": "PASS" if not problems else "FAIL",
        "paid_model_calls": 0, "problems": problems, "checks": checks,
        "source_sha256": {"revision_A": hashlib.sha256(SOURCE_A.encode()).hexdigest(),
                          "revision_B": hashlib.sha256(SOURCE_B.encode()).hexdigest()},
        "commits": {"revision_A": first, "revision_B": second},
    }
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    return result


def verify() -> dict:
    if not RESULT.exists():
        raise PilotFailure("offline pilot result is missing")
    result = json.loads(RESULT.read_text())
    if result.get("status") != "PASS" or result.get("paid_model_calls") != 0:
        raise PilotFailure(f"offline pilot is not a no-model pass: {result.get('problems')}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "verify"))
    args = parser.parse_args()
    result = run() if args.command == "run" else verify()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
