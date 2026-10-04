import json
import sys
import threading
import time
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "agent_verify"))

import ab
import budget
import run

CASES = [ROOT / f"fixtures/{c}/case.yaml" for c in
         ("authlib-jws-none", "caddy-forward-auth", "filebrowser-archive-backslash")]

# The one sentence PREREGISTRATION.md §8.1 allows the treatment prompt to add.
ADDED_SENTENCE = (
    " When a conclusion depends on a check, an overwrite, a transformation or any other behavior"
    " actually being executed, cite not only that behavior but also every key link on the way from"
    " the entry point to it. Keep quotes short, but short does not mean leaving out a link the"
    " conclusion depends on."
)


def test_treatment_prompt_is_control_plus_one_sentence():
    control = (ROOT / "experiments/agent_verify/prompt.md").read_text()
    treatment = (ROOT / "experiments/agent_verify/prompt_path.md").read_text()
    assert treatment.count(ADDED_SENTENCE) == 1
    assert treatment.replace(ADDED_SENTENCE, "") == control
    assert run.PROMPTS == {"control": control, "treatment": treatment}


def test_order_is_seeded_blocked_and_balanced(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    for out in (a, b):
        ab.order(Namespace(cases=CASES, seed=7, repeats=5, out=out))
    assert a.read_text() == b.read_text()  # reproducible from the seed
    pairs = run.read_order(a)
    assert len(pairs) == 160
    for i in range(0, 160, 2):  # every block is one control + one treatment on the same slot
        (arm1, slot1), (arm2, slot2) = pairs[i], pairs[i + 1]
        assert slot1 == slot2 and {arm1, arm2} == {"control", "treatment"}
    assert pairs[0][1].endswith("/r0") and pairs[-1][1].endswith("/r4")  # repeat-major


def test_blocks_finish_before_the_next_block_starts():
    class R:  # just enough of run.Run for slot_of()
        def __init__(self, slot, arm, seconds):
            case, hyp, cond, rep = slot.split("/")
            self.case = Namespace(id=case)
            self.hypothesis_id, self.condition, self.repeat = hyp, cond, int(rep[1:])
            self.arm, self.seconds = arm, seconds

    runs = [R("c/H1/forward/r0", "control", 0.05), R("c/H1/forward/r0", "treatment", 0.30),
            R("c/H1/swapped/r0", "treatment", 0.05), R("c/H1/swapped/r0", "control", 0.05)]
    events, lock = [], threading.Lock()

    def fn(r):
        with lock:
            events.append(("start", run.slot_of(r), time.monotonic()))
        time.sleep(r.seconds)
        with lock:
            events.append(("end", run.slot_of(r), time.monotonic()))
        return r.arm

    assert list(run.run_in_blocks(runs, fn, jobs=2)) == ["control", "treatment", "treatment", "control"]
    first_block_end = max(t for kind, slot, t in events if kind == "end" and slot.endswith("forward/r0"))
    second_block_start = min(t for kind, slot, t in events if kind == "start" and "swapped" in slot)
    assert second_block_start >= first_block_end  # the fast control did not run ahead


def test_budget_ceiling_is_shared_across_arms(tmp_path):
    d = tmp_path / "c/H1/forward/claude_m_high_control/r0"
    d.mkdir(parents=True)
    (d / "agent.jsonl").write_text(json.dumps({"type": "result", "total_cost_usd": 8.0}))
    guard = budget.LaunchGuard(tmp_path, "claude_m_high_*", cap=3, ceiling=10)
    ok, state = guard.reserve(tmp_path / "c/H1/forward/claude_m_high_treatment/r0")
    assert not ok and state["observed_spend"] == 8.0  # treatment sees control's spend


def _run(slot, arm, correct, path_ok, validity="VALID"):
    case, hyp, cond, rep = slot.split("/")
    return {
        "run": f"{case}/{hyp}/{cond}/claude_m_high_{arm}/{rep}", "case": case, "hypothesis": hyp,
        "validity": validity, "attribution_correct": correct,
        "evidence_complete_correct": correct and path_ok,
        "facts_covered": {"head-decode-reaches-verify@head": path_ok, "base-flip@base": True},
    }


CLEAN = {"anchor_audit_failures": 0, "accepted_revision_mismatches": 0, "harness_errors": 0,
         "runs_with_foreign_tools": 0, "runs_with_context_leak": 0, "infra_invalid_rate": 0.0}


def _compare(tmp_path, control, treatment, slots, harness=None):
    order = tmp_path / "order.txt"
    order.write_text("".join(f"control {s}\ntreatment {s}\n" for s in slots))
    paths = {}
    for arm, runs in (("control", control), ("treatment", treatment)):
        inv = (harness or {}).get(arm, CLEAN)
        paths[arm] = tmp_path / f"{arm}.json"
        paths[arm].write_text(json.dumps({"harness_invariants": inv, "runs": runs}))
    out = tmp_path / "cmp.json"
    ab.compare(Namespace(control=paths["control"], treatment=paths["treatment"], out=out, order=order))
    return json.loads(out.read_text())


SLOTS = [f"c/H{h}/forward/r{k}" for h in (1, 2) for k in range(5)]


def test_compare_success_on_strictly_valid_pairs(tmp_path):
    control = [_run(s, "control", True, i % 5 < 1) for i, s in enumerate(SLOTS)]
    treatment = [_run(s, "treatment", True, i % 5 < 4) for i, s in enumerate(SLOTS)]
    treatment[4]["validity"] = "SOMETHING_ELSE"  # anything but VALID drops the pair
    result = _compare(tmp_path, control, treatment, SLOTS)
    assert result["pairs"] == 9 and result["dropped_pairs"] == ["c/H1/forward/r4"]
    assert result["pairs_per_cell"] == {"c/H1/forward": 4, "c/H2/forward": 5}
    assert result["verdict"] == "SUCCESS" and result["experiment_success"] is True


def test_attribution_collapse_is_not_success(tmp_path):
    control = [_run(s, "control", True, False) for s in SLOTS]
    treatment = [_run(s, "treatment", i >= 6, True) for i, s in enumerate(SLOTS)]
    result = _compare(tmp_path, control, treatment, SLOTS)
    assert result["verdict"] == "FAIL" and not result["metric_success"]


def test_harness_invariant_blocks_success(tmp_path):
    control = [_run(s, "control", True, False) for s in SLOTS]
    treatment = [_run(s, "treatment", True, True) for s in SLOTS]
    result = _compare(tmp_path, control, treatment, SLOTS,
                      harness={"treatment": {**CLEAN, "harness_errors": 1}})
    assert result["metric_success"] is True
    assert result["verdict"] == "HARNESS_INVALID" and result["experiment_success"] is False
    assert result["harness"]["treatment"]["failing"] == {"harness_errors": 1}


def test_thin_or_missing_cells_are_inconclusive(tmp_path):
    designed = SLOTS + [f"c/H3/forward/r{k}" for k in range(5)]  # H3 never ran at all
    control = [_run(s, "control", True, False) for s in SLOTS]
    treatment = [_run(s, "treatment", True, True) for s in SLOTS]
    treatment[0]["validity"] = treatment[1]["validity"] = "INFRA_INVALID"  # H1 down to 3/5
    result = _compare(tmp_path, control, treatment, designed)
    assert result["verdict"] == "INCONCLUSIVE_INFRA"
    assert result["cells_below_minimum"] == {"c/H1/forward": 3, "c/H3/forward": 0}


def test_arm_selects_its_prompt_and_label(tmp_path, monkeypatch):
    from spike.models import CaseSpec
    monkeypatch.setattr(run, "RUNS", tmp_path)
    case = CaseSpec.load(CASES[0])
    r = run.Run(case, ROOT / case.repo.path, "H1", "forward", "claude", "claude-sonnet-5",
                "high", 3.0, 0, arm="treatment")
    r.dir.mkdir(parents=True)
    r.workdir = tmp_path
    cmd = run.claude_cmd(r, tmp_path / "session.json")
    assert run.PROMPTS["treatment"] in cmd and run.PROMPTS["control"] not in cmd
    assert r.label == "claude_claude-sonnet-5_high_treatment"


def test_no_valid_pairs_is_inconclusive_not_a_crash(tmp_path):
    control = [_run(s, "control", True, True, validity="INFRA_INVALID") for s in SLOTS]
    result = _compare(tmp_path, control, [], SLOTS)
    assert result["verdict"] == "INCONCLUSIVE_INFRA" and result["experiment_success"] is False
    assert result["pairs"] == 0 and result["criteria"] == {} and result["metric_success"] is False


def test_batch_stops_after_a_usage_limited_block():
    class R:
        def __init__(self, slot, arm):
            case, hyp, cond, rep = slot.split("/")
            self.case = Namespace(id=case)
            self.hypothesis_id, self.condition, self.repeat = hyp, cond, int(rep[1:])
            self.arm = arm

    runs = [R(s, a) for s in ("c/H1/forward/r0", "c/H1/swapped/r0", "c/H2/forward/r0")
            for a in ("control", "treatment")]
    fn = lambda r: f"INFRA_INVALID  {run.slot_of(r)} usage_limit exit=1" if r.condition == "swapped" \
        else f"VALID  {run.slot_of(r)} completed"
    lines = list(run.run_in_blocks(runs, fn, jobs=2, stop=lambda ls: any(" usage_limit " in x for x in ls)))
    assert len(lines) == 5 and lines[-1].startswith("STOP")  # the H2 block never launched
