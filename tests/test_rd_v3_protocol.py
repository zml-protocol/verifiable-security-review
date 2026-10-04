"""RD v3 offline treatment invariants: calibration, checkpoints, and split C."""

from __future__ import annotations

import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "experiments" / "rd" / "agent"
V3 = AGENT / "v3"
for directory in (V3, AGENT):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import schema as v2_schema  # noqa: E402
import rdv3_calibration as calibration  # noqa: E402
import rdv3_checkpoint as checkpoint  # noqa: E402
import rdv3_contract as contract  # noqa: E402
import rdv3_runner as runner  # noqa: E402
import rdv3_session as session  # noqa: E402
import rdv3_reference as reference  # noqa: E402
import rdv3_score as score  # noqa: E402
import rdv3_gate as gate  # noqa: E402
from spike.session import ToolInputError  # noqa: E402


def _git(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "RD V3"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "rd-v3@example.invalid"],
                   check=True)
    (repo / "p.go").write_text("package p\nfunc F(input string) {\n\tx := input\n\tsink(x)\n}\n")
    subprocess.run(["git", "-C", str(repo), "add", "p.go"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "a"], check=True)
    first = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True,
                           text=True, check=True).stdout.strip()
    (repo / "p.go").write_text(
        "package p\nfunc F(input string) {\n\tx := input\n\tif safe(x) {\n\t\tsink(x)\n\t}\n}\n")
    subprocess.run(["git", "-C", str(repo), "add", "p.go"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "b"], check=True)
    second = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True,
                            text=True, check=True).stdout.strip()
    return repo, first, second


def _anchor(line: int, expression: str) -> dict:
    return {"file": "p.go", "start_line": line, "end_line": line, "expression": expression}


def _requirements() -> dict:
    return {
        "entry": {revision: {"state": "present", "anchor": _anchor(3, "x := input")}
                  for revision in contract.REVISIONS},
        "behavior": {
            "revision_A": {"state": "present", "anchor": _anchor(4, "sink(x)")},
            "revision_B": {"state": "present", "anchor": _anchor(4, "if safe(x) {")},
        },
        "required_qualifiers": [],
        "rationale": "entry and deciding behavior",
    }


def _analysis(tmp_path: Path, first: str, second: str) -> dict[str, str]:
    paths = {}
    for revision, commit in (("revision_A", first), ("revision_B", second)):
        doc = {"status": "ok", "commit": commit,
               "shapes": [["file", "p.go", 1, 1, 7], ["parameter", "p.go", 2, 8, 2],
                          ["definition", "p.go", 3, 2, 3], ["definition", "p.go", 4, 2, 4]],
               "rows": {"def_use": [["p.go", 2, 8, "p.go", 3, 2],
                                    ["p.go", 3, 2, "p.go", 4, 2]]}}
        path = tmp_path / f"{revision}.json.gz"
        path.write_bytes(gzip.compress(json.dumps(doc).encode(), mtime=0))
        paths[revision] = str(path)
    return paths


def _config(tmp_path: Path, phase: str, repo: Path, first: str, second: str,
            *, analysis: dict[str, str] | None = None, c_stage: str | None = None,
            out_name: str | None = None) -> session.V3Config:
    return session.V3Config(
        session_id=f"v3-test/{phase}/{c_stage or 'main'}", task_id="task-v3", phase=phase,
        c_stage=c_stage, language="go",
        claim={"package": "p", "effect_claim": "attacker input may reach an unsafe sink"},
        repo=str(repo), revisions={"revision_A": first, "revision_B": second},
        out_dir=str(tmp_path / (out_name or f"phase-{phase}")),
        artifact_dir=str(tmp_path / "artifacts"), analysis=analysis or {},
        provider_sha256="a" * 64 if phase == "b" else "",
        relation_table_sha256="b" * 64 if phase == "b" else "",
    )


def test_c2_schema_is_exclusive_and_allows_abstention():
    assert contract.cwe_taxonomy({"ranked_cwes": ["CWE-79", "CWE-89"]})["ranked_cwes"] \
        == ["CWE-79", "CWE-89"]
    assert contract.cwe_taxonomy({"result": "NO_CONFIDENT_CWE"})["result"] \
        == "NO_CONFIDENT_CWE"
    for bad in ({"ranked_cwes": []}, {"ranked_cwes": ["79"]},
                {"ranked_cwes": ["CWE-79", "CWE-79"]},
                {"ranked_cwes": ["CWE-79"], "result": "NO_CONFIDENT_CWE"}):
        with pytest.raises(contract.V3SchemaError):
            contract.cwe_taxonomy(bad)


def test_calibration_is_language_scoped_and_covers_every_cell():
    for language in ("go", "python"):
        rows = calibration.examples(language)
        assert len(rows) == 5 and len({row["cell"] for row in rows}) == 5
        assert all("CWE" not in json.dumps(row) for row in rows)


def test_a_task_exposes_effect_only_and_five_worked_examples(tmp_path):
    repo, first, second = _git(tmp_path)
    phase = session.V3Session(_config(tmp_path, "a", repo, first, second))
    task = phase.call("get_task")
    assert "CWE-" not in json.dumps(task)
    assert len(task["schema_calibration"]["examples"]) == 5
    assert phase.call("submit_requirements", requirements=_requirements())["locked"] == "A"


def test_b_checkpoints_every_outcome_and_terminal_input_reaches_split_c(tmp_path):
    repo, first, second = _git(tmp_path)
    analyses = _analysis(tmp_path, first, second)
    phase_a = session.V3Session(_config(tmp_path, "a", repo, first, second))
    phase_a.call("submit_requirements", requirements=_requirements())

    phase_b = session.V3Session(_config(tmp_path, "b", repo, first, second, analysis=analyses))
    confirmed = {"revision": "revision_A", "relation": "def_use",
                 "from": _anchor(2, "input"), "to": _anchor(3, "x := input")}
    assert phase_b.call("check_hop", hop=confirmed) == {"feedback": "confirmed"}
    unverified = {**confirmed, "from": _anchor(3, "x := input")}
    assert phase_b.call("check_hop", hop=unverified) == {"feedback": "not confirmed"}
    malformed = {**confirmed, "to": _anchor(5, "}")}
    with pytest.raises(ToolInputError, match="must name"):
        phase_b.call("check_hop", hop=malformed)

    events = checkpoint.load_and_verify_events(tmp_path / "artifacts" / "b-checkpoints")
    assert [event["resolution"]["state"] for event in events] == [
        "VERIFIED", "UNVERIFIED", "REJECTED_STRUCTURAL"]
    third = tmp_path / "artifacts" / "b-checkpoints" / "events" / "000003.json"
    noncanonical = third.with_name("000004.json")
    third.rename(noncanonical)
    with pytest.raises(checkpoint.CheckpointError, match="non-canonical"):
        checkpoint.load_and_verify_events(tmp_path / "artifacts" / "b-checkpoints")
    noncanonical.rename(third)
    partial = checkpoint.materialize(
        tmp_path / "artifacts" / "b-checkpoints",
        tmp_path / "artifacts" / "partial-checkpoint.json")
    assert partial["event_count"] == 3 and len(partial["verified_graph"]) == 1
    assert partial["last_successful_event"] == 1
    graph_scorer = score.graph.GraphScorer(
        language="go", repo=str(repo),
        revisions={"revision_A": first, "revision_B": second},
        analysis=score.graph.load_analysis(analyses))
    a_artifact = json.loads((tmp_path / "artifacts" / "a.json").read_text())
    diagnostics = score.checkpoint_diagnostics(graph_scorer, a_artifact, partial)
    assert diagnostics["last_successful_event"] == 1
    assert diagnostics["revisions"]["revision_A"]["verified_edges"] == 1
    assert not diagnostics["checkpoint_already_full_chain"]
    terminal = checkpoint.materialize_terminal_b(tmp_path / "artifacts")
    assert terminal["status"] == "B_TERMINAL_NO_SUBMIT"

    c1 = session.V3Session(_config(tmp_path, "c", repo, first, second,
                                   c_stage="c1", out_name="phase-c1"))
    assert set(c1._tools) == {"get_task", "submit_effect_attribution"}
    assert c1.call("get_task")["stage"] == "C1_EFFECT_ATTRIBUTION"
    locked_c1 = c1.call("submit_effect_attribution", conclusion={
        "revision_A": "SUPPORTED", "revision_B": "NOT_SUPPORTED"})
    assert locked_c1["locked"] == "C1"

    c2 = session.V3Session(_config(tmp_path, "c", repo, first, second,
                                   c_stage="c2", out_name="phase-c2"))
    assert set(c2._tools) == {"get_task", "submit_cwe_taxonomy"}
    task = c2.call("get_task")
    assert task["stage"] == "C2_CWE_TAXONOMY" and "target" not in task
    locked_c2 = c2.call("submit_cwe_taxonomy", taxonomy={"result": "NO_CONFIDENT_CWE"})
    assert locked_c2["locked"] == "C2"
    for name in ("c1", "c2"):
        contract.verify_seal(json.loads((tmp_path / "artifacts" / f"{name}.json").read_text()))


def test_c2_cannot_start_before_c1(tmp_path):
    repo, first, second = _git(tmp_path)
    phase_a = session.V3Session(_config(tmp_path, "a", repo, first, second))
    phase_a.call("submit_requirements", requirements=_requirements())
    artifacts = tmp_path / "artifacts"
    partial = contract.sealed({
        "schema": "rd-v3-b-partial-checkpoint/v1", "task_id": "task-v3",
        "a_seal": json.loads((artifacts / "a.json").read_text())["seal"],
        "provider_sha256": "a" * 64, "relation_table_sha256": "b" * 64,
        "event_count": 0, "last_event_sha256": None,
        "graph_state_sha256": contract.seal({"verified_hops": []}),
        "checked_hops": [], "verified_graph": []})
    (artifacts / "partial-checkpoint.json").write_text(json.dumps(partial))
    terminal = contract.sealed({
        "schema": "rd-v3-b-terminal/v1", "task_id": "task-v3", "a_seal": partial["a_seal"],
        "status": "B_TERMINAL_NO_SUBMIT", "partial_checkpoint_seal": partial["seal"],
        "partial_checkpoint": {key: value for key, value in partial.items() if key != "seal"}})
    (artifacts / "b-terminal.json").write_text(json.dumps(terminal))
    with pytest.raises(ToolInputError, match="before C1"):
        session.V3Session(_config(tmp_path, "c", repo, first, second,
                                  c_stage="c2", out_name="phase-c2"))


def test_final_b_and_checkpoint_remain_distinct(tmp_path):
    repo, first, second = _git(tmp_path)
    analyses = _analysis(tmp_path, first, second)
    phase_a = session.V3Session(_config(tmp_path, "a", repo, first, second))
    phase_a.call("submit_requirements", requirements=_requirements())
    phase_b = session.V3Session(_config(tmp_path, "b", repo, first, second, analysis=analyses))
    hop = {"revision": "revision_A", "relation": "def_use",
           "from": _anchor(2, "input"), "to": _anchor(3, "x := input")}
    phase_b.call("check_hop", hop=hop)
    assert phase_b.call("submit_evidence", hops=[hop])["locked"] == "B"
    partial = checkpoint.materialize(
        tmp_path / "artifacts" / "b-checkpoints",
        tmp_path / "artifacts" / "partial-checkpoint.json")
    selected = checkpoint.materialize_terminal_b(tmp_path / "artifacts")
    assert selected["schema"] == "rd-b/v1"
    assert partial["schema"] == "rd-v3-b-partial-checkpoint/v1"
    assert not (tmp_path / "artifacts" / "b-terminal.json").exists()


def test_runner_freezes_per_task_budget_and_shared_c_envelope(tmp_path):
    files = {"b.yaml": "2" * 64, "a.yaml": "1" * 64}
    assert gate.aggregate(files) == gate.aggregate(dict(reversed(list(files.items()))))
    assert score.conditional_metric(0, 0)["status"] == "B_CONDITIONAL_NOT_ESTIMABLE"
    assert score.conditional_metric(1, 2)["status"] == "B_CONDITIONAL_UNDERPOWERED"
    assert score.conditional_metric(2, 3)["status"] == "B_CONDITIONAL_ESTIMABLE"
    tasks = [
        {"task_id": f"real-{number}", "task_kind": "real",
         "language": "go" if number <= 3 else "python"}
        for number in range(1, 7)
    ]
    tasks.append({"task_id": "control-1", "task_kind": "negative_control",
                  "language": "go", "parent_real_task_id": "real-1"})
    manifest = {"schema": "rd-v3-run-manifest/v1", "protocol": "rd-v3", "mode": "formal",
                "formal_task_count": 7, "tasks": tasks, "launch_ceiling_usd": 49.0,
                "user_authorization_usd": 49.0, "realized_real_tasks": 6,
                "qualified_negative_control_tasks": 1}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    assert len(runner.load_manifest(path)["tasks"]) == 7
    assert runner.PHASE_BUDGET == {"a": 3.0, "b": 3.0, "c1": 1.0, "c2": 0.0}
    assert runner.SESSION_CAP == {"a": 3.0, "b": 6.0, "c1": 7.0, "c2": 7.0}
    manifest["user_authorization_usd"] = 48.99
    path.write_text(json.dumps(manifest))
    with pytest.raises(runner.RunnerError, match="FORMAL_NOT_STARTED_BUDGET_AUTHORIZATION"):
        runner.load_manifest(path)

    manifest["user_authorization_usd"] = 49.0
    manifest["qualified_negative_control_tasks"] = 0
    path.write_text(json.dumps(manifest))
    with pytest.raises(runner.RunnerError, match="negative-control task count drift"):
        runner.load_manifest(path)

    attempt = tmp_path / "runs" / "task-x" / "attempt-1"
    for stage, cost in (("a", 0.2), ("b", 0.5), ("c1", 0.7), ("c2", 0.8)):
        directory = attempt / f"stage-{stage}"
        directory.mkdir(parents=True)
        (directory / "agent.jsonl").write_text(json.dumps({
            "type": "result", "total_cost_usd": cost}) + "\n")
    assert runner.observed_spend(tmp_path / "runs") == pytest.approx(0.8)
    status, reason = runner.execute_stage(
        {}, "a", tmp_path / "runs" / "task-y" / "attempt-1", tmp_path,
        "unused", {}, {}, run_root=tmp_path / "runs", launch_ceiling=3.0)
    assert (status, reason) == ("BUDGET_CENSORED", "launch ceiling $3")


def test_synthetic_gate_terminal_status_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "GATE_RESULT", tmp_path / "combined.json")
    a_path, provider_path = tmp_path / "a.json", tmp_path / "provider.json"
    a = {"commitment_sha256": "c" * 64, "status": "A_CALIBRATION_FAILED",
         "harness_invariant_failures": {}}
    provider_result = {"commitment_sha256": "c" * 64, "status": "PASS"}
    a_path.write_text(json.dumps(a))
    provider_path.write_text(json.dumps(provider_result))
    assert gate.combine(a_path, provider_path)["status"] == "A_CALIBRATION_FAILED"

    a["status"] = "CALIBRATION_INVALID"
    a_path.write_text(json.dumps(a))
    assert gate.combine(a_path, provider_path)["status"] == "CALIBRATION_INVALID"

    provider_result["status"] = "UNSAFE_PROVIDER"
    provider_path.write_text(json.dumps(provider_result))
    assert gate.combine(a_path, provider_path)["status"] == "UNSAFE_PROVIDER"


def test_reference_audit_uses_manifest_mapping_and_distinguishes_dispositions(tmp_path):
    repo, first, second = _git(tmp_path)
    analyses = _analysis(tmp_path, first, second)
    truth = {
        "items": [
            {"id": "entry", "kind": "entry", "entry": {
                "vuln": {"state": "present", "anchor": _anchor(3, "x := input")},
                "fixed": {"state": "present", "anchor": _anchor(3, "x := input")}}},
            {"id": "behavior", "kind": "behavior", "behavior": {
                "vuln": {"state": "present", "anchor": _anchor(4, "sink(x)")},
                "fixed": {"state": "present", "anchor": _anchor(4, "if safe(x) {")}}},
        ]}
    truth_path = tmp_path / "truth.yaml"
    truth_path.write_text(yaml.safe_dump(truth, sort_keys=False))
    task = {"task_id": "real-1", "task_kind": "real", "fixture": "fresh-fixture",
            "language": "go", "repo": str(repo),
            "revisions": {"revision_A": first, "revision_B": second},
            "canonical_to_outward": {"vuln": "revision_A", "fixed": "revision_B"},
            "truth_path": str(truth_path), "analysis": analyses}

    def hops(revision: str) -> list[dict]:
        behavior = _anchor(4, "sink(x)" if revision == "revision_A" else "if safe(x) {")
        return [
            {"relation": "def_use", "from": _anchor(2, "input"),
             "to": _anchor(3, "x := input")},
            {"relation": "def_use", "from": _anchor(3, "x := input"), "to": behavior},
        ]

    evidence = {"schema": "rd-v3-reference-evidence/v1", "task_id": "real-1",
                "fixture": "fresh-fixture", "revisions": {
                    "vuln": {"chain_required": True, "semantic_chain_complete": True,
                             "hops": hops("revision_A")},
                    "fixed": {"chain_required": True, "semantic_chain_complete": True,
                              "hops": hops("revision_B")}}}
    evidence_path = tmp_path / "evidence.yaml"
    evidence_path.write_text(yaml.safe_dump(evidence, sort_keys=False))
    assert reference.audit(task, evidence_path)["disposition"] == reference.FULL
    assert score.score_a(task, {"requirements": _requirements()})["truth_matching"]
    label, canonical = score.attribution(
        {"revision_A": "SUPPORTED", "revision_B": "NOT_SUPPORTED"},
        task["canonical_to_outward"])
    assert label == "FIX_IMPLICATED" and canonical["vuln"] == "SUPPORTED"

    evidence["revisions"]["vuln"]["hops"][1]["to"] = _anchor(3, "x := input")
    evidence_path.write_text(yaml.safe_dump(evidence, sort_keys=False))
    assert reference.audit(task, evidence_path)["disposition"] == reference.BLIND

    evidence["revisions"]["vuln"]["semantic_chain_complete"] = False
    evidence_path.write_text(yaml.safe_dump(evidence, sort_keys=False))
    assert reference.audit(task, evidence_path)["disposition"] == reference.UNREALIZABLE
