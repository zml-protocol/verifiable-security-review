"""Write or verify the pre-held-out RD v3 treatment freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[3]
for directory in (HERE, PARENT):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import rdv3_contract as contract  # noqa: E402
import rdv3_pilot as pilot  # noqa: E402
import rdv3_provider_dev as provider_dev  # noqa: E402
import rdv3_runner as runner  # noqa: E402

PRIOR_FREEZE = HERE / "treatment-freeze.json"
FREEZE = HERE / "treatment-freeze-v2.json"


class FreezeError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tracked(path: Path) -> bool:
    result = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch",
                             str(path.relative_to(ROOT))], capture_output=True, check=False)
    return result.returncode == 0


def protocol_files() -> list[Path]:
    files = [PARENT / name for name in (
        "V3-PROTOCOL-DELTA.md", "V3-FINAL-REVIEW.md", "schema.py", "source.py", "session.py",
        "analysis.py", "graph.py", "verifiability.py",
    )]
    files += [HERE / name for name in (
        "CONSTRUCTION-SPEC.md", "CONSTRUCTION-ERRATUM.md", "HELDOUT-CURATOR-CONTRACT.md",
        "TREATMENT-FREEZE-ERRATUM.md",
        "construction-freeze-v2.json", "treatment-freeze.json",
        "construction_freeze_v2.py", "a-development.yaml", "a-heldout-spec.yaml",
        "provider-development-v2.yaml", "provider-heldout-spec.yaml", "selection-seed-spec.yaml",
        "prompt-a.md", "prompt-b.md", "prompt-c1.md", "prompt-c2.md",
        "rdv3_analysis.py", "rdv3_calibration.py", "rdv3_checkpoint.py", "rdv3_contract.py",
        "rdv3_freeze.py", "rdv3_gate.py", "rdv3_mcp_server.py", "rdv3_pilot.py", "rdv3_provider_dev.py",
        "rdv3_reference.py", "rdv3_runner.py", "rdv3_score.py", "rdv3_session.py",
    )]
    files += sorted((HERE / "queries").rglob("*"))
    files += [ROOT / name for name in (
        "pyproject.toml", "uv.lock", "tests/test_rd_agent.py", "tests/test_rd_protocol.py",
        "tests/test_rd_v3_protocol.py", "experiments/rd/agent/freeze.json",
        "experiments/agent_verify/validity.py", "experiments/rd/truth/agreement.py",
        "experiments/rd/truth/matcher.py", "experiments/rd/truth/resolver.py",
        "experiments/rd/truth/vocabulary.py", "experiments/hop_verify/relations.yaml",
        "experiments/hop_bridge/relations.yaml", "experiments/hop_chain/chain.py",
        "experiments/hop_chain/connector.py", "src/spike/anchors.py", "src/spike/gitrepo.py",
        "src/spike/hops.py", "src/spike/linemap.py", "src/spike/models.py",
        "src/spike/session.py",
    )]
    files += sorted((ROOT / "experiments" / "hop_verify" / "queries").rglob("*.ql*"))
    files += sorted((ROOT / "experiments" / "hop_bridge" / "queries").rglob("*.ql*"))
    seen = set()
    return [path for path in files if path.is_file()
            and not (str(path) in seen or seen.add(str(path)))]


def provider_files() -> list[Path]:
    selected = [PARENT / name for name in ("analysis.py", "graph.py", "session.py", "verifiability.py")]
    selected += [HERE / "rdv3_analysis.py", *sorted((HERE / "queries").rglob("*"))]
    selected += [ROOT / name for name in (
        "experiments/hop_verify/relations.yaml", "experiments/hop_bridge/relations.yaml",
        "experiments/hop_chain/chain.py", "experiments/hop_chain/connector.py",
        "src/spike/hops.py",
    )]
    selected += sorted((ROOT / "experiments" / "hop_verify" / "queries").rglob("*.ql*"))
    selected += sorted((ROOT / "experiments" / "hop_bridge" / "queries").rglob("*.ql*"))
    return [path for path in selected if path.is_file()]


def provider_development() -> dict:
    if not provider_dev.RESULT.exists():
        raise FreezeError("provider development result is missing")
    result = json.loads(provider_dev.RESULT.read_text())
    if result.get("schema") != "rd-v3-provider-development-result/v1":
        raise FreezeError("bad provider development result schema")
    if result.get("corpus_sha256") != sha256(provider_dev.CORPUS):
        raise FreezeError("provider development corpus drift")
    if result.get("unsafe") is not False or len(result.get("targets") or []) != 3:
        raise FreezeError("provider development did not produce the frozen safe target set")
    for target in result["targets"]:
        if target.get("disposition") != "SUPPORTED":
            raise FreezeError(f"provider development target is not supported: {target.get('target')}")
        true_rows = [row for row in target["edges"] if row["truth"]]
        false_rows = [row for row in target["edges"] if not row["truth"]]
        if len(true_rows) != 2 or len(false_rows) != 2 \
                or any(row["state"] != "VERIFIED" for row in true_rows) \
                or any(row["state"] == "VERIFIED" for row in false_rows):
            raise FreezeError(f"provider development edge gate failed: {target.get('target')}")
        analysis = provider_dev.OUT / target["target"] / "analysis" / "analysis.json.gz"
        if not analysis.exists() or sha256(analysis) != target.get("analysis_sha256"):
            raise FreezeError(f"provider development analysis drift: {target.get('target')}")
    return result


def _file_hashes(paths: list[Path]) -> dict[str, str]:
    missing = [str(path) for path in paths if not path.exists()]
    untracked = [str(path.relative_to(ROOT)) for path in paths if path.exists() and not _tracked(path)]
    if missing:
        raise FreezeError(f"missing treatment files: {missing}")
    if untracked:
        raise FreezeError(f"treatment files must be committed before freeze: {untracked}")
    return {str(path.relative_to(ROOT)): sha256(path) for path in paths}


def build() -> dict:
    if not PRIOR_FREEZE.exists():
        raise FreezeError("the incomplete v1 treatment freeze is missing")
    tracked_dirty = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"],
        capture_output=True, text=True, check=True).stdout.strip()
    if tracked_dirty:
        raise FreezeError("tracked working tree must be clean before treatment freeze")
    files = _file_hashes(protocol_files())
    provider_hashes = _file_hashes(provider_files())
    relation_paths = [ROOT / "experiments/hop_verify/relations.yaml",
                      ROOT / "experiments/hop_bridge/relations.yaml"]
    relation_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in relation_paths}
    development = provider_development()
    pilot_result = pilot.verify()
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                            text=True, check=True).stdout.strip()
    return {
        "schema": "rd-v3-treatment-freeze/v2", "protocol": runner.PROTOCOL,
        "status": "TREATMENT_FROZEN", "created_from_commit": commit,
        "supersedes": str(PRIOR_FREEZE.relative_to(ROOT)),
        "superseded_status": "PRE_GATE_INCOMPLETE",
        "provider_sha256": contract.seal(provider_hashes),
        "relation_table_sha256": contract.seal(relation_hashes),
        "execution": {"model": runner.MODEL, "effort": runner.EFFORT,
                      "claude_code_version": runner.CLI_VERSION,
                      "phase_budget_usd": runner.PHASE_BUDGET,
                      "cumulative_session_cap_usd": runner.SESSION_CAP,
                      "phase_timeout_seconds": runner.TIMEOUT,
                      "heldout_launch_ceiling_usd": 60.0,
                      "formal_launch_formula": "7 * formal_task_count",
                      "formal_launch_max_usd": 84.0},
        "gates": {"a_cases": 20, "a_min_exact": 16,
                  "a_cell_and_structural_guards": True,
                  "provider_false_verified_max": 0,
                  "provider_partial_or_unsupported_allowed": True,
                  "provider_infrastructure_attempts_max": 2},
        "files": files, "provider_files": provider_hashes,
        "relation_tables": relation_hashes,
        "provider_development": {
            "result_sha256": sha256(provider_dev.RESULT),
            "corpus_sha256": development["corpus_sha256"],
            "target_dispositions": {row["target"]: row["disposition"]
                                    for row in development["targets"]}},
        "offline_pilot": {"result_sha256": sha256(pilot.RESULT),
                          "paid_model_calls": pilot_result["paid_model_calls"],
                          "source_sha256": pilot_result["source_sha256"]},
    }


def write() -> None:
    value = build()
    FREEZE.write_text(json.dumps(value, indent=2) + "\n")
    print(f"wrote {FREEZE.relative_to(ROOT)} with {len(value['files'])} file hashes")


def verify() -> dict:
    if not FREEZE.exists():
        raise FreezeError("treatment freeze is missing")
    frozen = json.loads(FREEZE.read_text())
    if frozen.get("schema") != "rd-v3-treatment-freeze/v2" \
            or frozen.get("status") != "TREATMENT_FROZEN":
        raise FreezeError("bad treatment freeze header")
    problems = []
    for name, expected in frozen.get("files", {}).items():
        path = ROOT / name
        if not path.exists() or sha256(path) != expected:
            problems.append(f"file drift: {name}")
    provider_hashes = {name: sha256(ROOT / name) for name in frozen.get("provider_files", {})
                       if (ROOT / name).exists()}
    if provider_hashes != frozen.get("provider_files") \
            or contract.seal(provider_hashes) != frozen.get("provider_sha256"):
        problems.append("provider drift")
    relation_hashes = {name: sha256(ROOT / name) for name in frozen.get("relation_tables", {})
                       if (ROOT / name).exists()}
    if relation_hashes != frozen.get("relation_tables") \
            or contract.seal(relation_hashes) != frozen.get("relation_table_sha256"):
        problems.append("relation-table drift")
    try:
        development = provider_development()
        if sha256(provider_dev.RESULT) != frozen.get("provider_development", {}).get("result_sha256") \
                or development.get("corpus_sha256") != frozen.get("provider_development", {}).get("corpus_sha256"):
            problems.append("provider development result drift")
    except FreezeError as exc:
        problems.append(str(exc))
    try:
        pilot.verify()
        if sha256(pilot.RESULT) != frozen.get("offline_pilot", {}).get("result_sha256"):
            problems.append("offline pilot result drift")
    except pilot.PilotFailure as exc:
        problems.append(str(exc))
    if problems:
        raise FreezeError("; ".join(problems))
    return frozen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("write", "verify"))
    args = parser.parse_args()
    if args.command == "write":
        write()
    else:
        frozen = verify()
        print(json.dumps({"status": "OK", "protocol": frozen["protocol"],
                          "created_from_commit": frozen["created_from_commit"]}, indent=2))


if __name__ == "__main__":
    main()
