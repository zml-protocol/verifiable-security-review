"""Nothing answer-bearing may reach the agent: not case notes, goldens, case ids or CVE ids."""

import json
import re
import sys
from pathlib import Path

import pytest

from spike.mcp_server import INSTRUCTIONS
from spike.models import CaseSpec, SessionConfig
from spike.session import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "agent_verify"))
from score import context_leaks

REAL_CASES = ["authlib-jws-none", "caddy-forward-auth", "filebrowser-archive-backslash"]


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[A-Za-z0-9_-]{8,}", text)}


@pytest.mark.parametrize("case_id", REAL_CASES)
def test_agent_payload_carries_no_answers(case_id, tmp_path):
    case = CaseSpec.load(ROOT / "fixtures" / case_id / "case.yaml")
    golden_text = (ROOT / "fixtures" / case_id / "golden.yaml").read_text()
    if not (ROOT / case.repo.path).exists():
        pytest.skip("fixture repository not cloned")
    for hyp in case.hypotheses:
        config = SessionConfig(
            session_id="t", repo=str(ROOT / case.repo.path),
            revisions={"base": case.base, "head": case.head}, hypothesis=hyp,
            deny_paths=case.deny_paths, out_dir=str(tmp_path / hyp.id),
        )
        task = Session(config).call("get_task")
        payload = json.dumps(task) + INSTRUCTIONS
        assert case_id not in payload
        assert not re.search(r"CVE-\d{4}-\d+|GHSA-", payload)
        assert "golden" not in payload.lower()
        # nothing distinctive from the case notes or the golden reaches the agent,
        # beyond the hypothesis itself and the fixed harness wording
        boilerplate = {k: v for k, v in task.items() if k != "hypothesis"}
        allowed = _words(json.dumps(hyp.model_dump())) | _words(json.dumps(boilerplate) + INSTRUCTIONS)
        leaked = (_words(case.notes) | _words(golden_text)) & _words(payload)
        assert leaked <= allowed, leaked - allowed


def test_context_leak_detection(tmp_path):
    inside = {"type": "system", "subtype": "init", "cwd": str(ROOT / "runs" / "x")}
    outside = {"type": "system", "subtype": "init", "cwd": str(tmp_path)}
    assert context_leaks([inside]) == ["cwd_inside_harness_repo"]
    assert context_leaks([outside]) == []
    mem = tmp_path / "memory"
    mem.mkdir()
    (mem / "MEMORY.md").write_text("x")
    assert context_leaks([{**outside, "memory_paths": {"auto": str(mem)}}]) == [
        "auto_memory_not_empty"
    ]


def test_run_identity_must_not_reach_the_agent(tmp_path):
    import score
    run_dir = score.RUNS / "v2/c/H1/forward/claude_m_high_treatment/r0"
    clean = {"type": "system", "subtype": "init", "cwd": str(tmp_path)}
    assert context_leaks([clean], run_dir, [{"result": {"code": "x"}}]) == []
    leaky = {**clean, "cwd": "/tmp/claude_m_high_treatment"}
    assert context_leaks([leaky], run_dir) == ["run_identity_in_init"]
    result = [{"result": {"note": f"see {score.RUNS}/v2"}}]
    assert context_leaks([clean], run_dir, result) == ["run_identity_in_tool_results"]
    code = [{"result": {"code": "    h.cache_control = true"}}]  # source code is not a leak
    assert context_leaks([clean], run_dir, code) == []
