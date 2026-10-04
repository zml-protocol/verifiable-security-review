import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "agent_verify"))

from score import fact_covered
from validity import INFRA_INVALID, VALID, classify

from spike.anchors import Anchor
from spike.models import Fact


def anchor(rev, path, lo, hi):
    return Anchor(id="A", revision=rev, path=path, start_line=lo, end_line=hi, sha256="")


def test_fact_needs_every_location_of_one_set():
    fact = Fact.model_validate({
        "id": "f", "revision": "head", "component": "control", "statement": "",
        "evidence_sets": [
            [{"path": "a.py", "lines": 17}, {"path": "svc.py", "lines": "14-15"}],
            [{"path": "alt.py", "lines": 3}],
        ],
    })
    assert not fact_covered(fact, [anchor("head", "a.py", 16, 18)])
    assert fact_covered(fact, [anchor("head", "a.py", 16, 18), anchor("head", "svc.py", 15, 15)])
    assert fact_covered(fact, [anchor("head", "alt.py", 1, 40)])
    assert not fact_covered(fact, [anchor("base", "alt.py", 1, 40)])  # wrong revision


def _run_dir(tmp_path, events, state=True, meta=None, transcript=True):
    d = tmp_path / "r0"
    d.mkdir(parents=True)
    (d / "agent.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    (d / "meta.json").write_text(json.dumps(meta or {"exit": 0}))
    if state:
        (d / "state.json").write_text("{}")
    if transcript:
        (d / "transcript.jsonl").write_text('{"seq": 1}\n')
    return d


INIT = {"type": "system", "subtype": "init", "model": "claude-haiku-4-5-20251001"}


def test_classify_agent_side_failures_count(tmp_path):
    budget = {"type": "result", "subtype": "error_max_budget_usd", "errors": ["Reached maximum budget ($1)"]}
    assert classify(_run_dir(tmp_path, [INIT, budget])) == (VALID, "error_max_budget_usd")


def test_classify_refusal_counts(tmp_path):
    refusal = {"type": "assistant", "message": {"stop_reason": "refusal", "content": []}}
    assert classify(_run_dir(tmp_path, [INIT, refusal]))[1] == "refusal"


def test_classify_infrastructure_failures(tmp_path):
    api = {"type": "result", "subtype": "error_during_execution", "errors": ["API Error: 529 overloaded"]}
    assert classify(_run_dir(tmp_path / "a", [INIT, api])) == (INFRA_INVALID, "api_error")
    assert classify(_run_dir(tmp_path / "b", [], state=False))[0] == INFRA_INVALID
    assert classify(_run_dir(tmp_path / "c", []))[1] == "agent_not_started"
    stalled = _run_dir(tmp_path / "d", [INIT], meta={"exit": "timeout"}, transcript=False)
    assert classify(stalled) == (INFRA_INVALID, "agent_stalled")
    slow = _run_dir(tmp_path / "e", [INIT], meta={"exit": "timeout"})
    assert classify(slow) == (VALID, "timeout")


def test_classify_usage_limit_reported_as_success(tmp_path):
    limited = {"type": "result", "subtype": "success", "is_error": True, "total_cost_usd": 0,
               "result": "You've hit your weekly limit · resets Oct 2, 10pm (America/New_York)"}
    assert classify(_run_dir(tmp_path, [INIT, limited])) == (INFRA_INVALID, "usage_limit")
    ok = {"type": "result", "subtype": "success", "is_error": False, "result": "done"}
    assert classify(_run_dir(tmp_path / "ok", [INIT, ok])) == (VALID, "completed")
