import json
import sys
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "agent_verify"))

import budget
from budget import LaunchGuard, run_cost, spent

LABEL = "claude_m"


def attempt(root: Path, slot: str, cost: float | None, meta: bool = True):
    case, hyp, cond, rep = slot.split("/")
    d = root / case / hyp / cond / LABEL / rep
    d.mkdir(parents=True)
    if meta:
        (d / "meta.json").write_text("{}")
    events = [{"type": "system", "subtype": "init"}]
    if cost is not None:
        events.append({"type": "result", "subtype": "success", "total_cost_usd": cost})
    (d / "agent.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    return d


def test_cost_and_spend(tmp_path):
    attempt(tmp_path, "c/H1/forward/r0", 0.5)
    attempt(tmp_path, "c/H1/forward/r0.invalid1", None)  # never reported: counts as the cap
    attempt(tmp_path, "c/H2/forward/r0", None, meta=False)  # died before meta.json: still charged
    assert run_cost(tmp_path / "c/H1/forward" / LABEL / "r0", 3) == 0.5
    assert spent(tmp_path, LABEL, 3) == 6.5


def test_launch_guard_reserves_in_flight(tmp_path):
    attempt(tmp_path, "c/H1/forward/r0", 3.0)
    guard = LaunchGuard(tmp_path, LABEL, cap=3, ceiling=10)
    a, b, c = (tmp_path / n for n in "abc")
    assert guard.reserve(a)[0]  # 3 + 3 <= 10
    assert guard.reserve(b)[0]  # 3 + 6 <= 10
    ok, state = guard.reserve(c)  # 3 + 9 > 10
    assert not ok and state["in_flight"] == 2
    guard.release(a)
    assert guard.reserve(c)[0]


def test_in_flight_log_is_not_double_counted(tmp_path):
    running = attempt(tmp_path, "c/H1/forward/r0", None, meta=False)  # partial log, no result yet
    guard = LaunchGuard(tmp_path, LABEL, cap=3, ceiling=6)
    assert guard.reserve(running)[0]
    ok, state = guard.reserve(tmp_path / "next")
    assert ok and state == {"observed_spend": 0, "in_flight": 1}


def test_plan_trims_identity_base_then_repeats(tmp_path, monkeypatch):
    runs = tmp_path / "runs" / "agent_verify" / "v1.1"
    gate = ["authlib-jws-none/H1/forward/r0", "caddy-forward-auth/H1/forward/r0"]
    for slot, cost in zip(gate, (0.4, 1.0)):
        attempt(runs, slot, cost)
    (tmp_path / "gate.txt").write_text("# gate\n" + "\n".join(gate) + "\n")
    monkeypatch.setattr(budget, "ROOT", tmp_path)
    cases = [ROOT / f"fixtures/{c}/case.yaml" for c in
             ("authlib-jws-none", "caddy-forward-auth", "filebrowser-archive-backslash")]
    args = Namespace(protocol="v1.1", cases=cases, gate=tmp_path / "gate.txt", label=LABEL,
                     cap=3.0, ceiling=100.0, buffer=0.10, repeats=5)
    budget.plan(args)
    result = json.loads((runs / "budget_plan.json").read_text())
    # 8 hypotheses x 4 x 5 = 160 slots at 1.1/run cannot fit 100: identity_base goes first,
    # then repeats shrink symmetrically until the projection fits.
    assert result["trim_steps"][0] == "drop condition identity_base"
    assert result["conditions"] == ["forward", "swapped", "identity_head"]
    assert result["projected_total_usd"] <= 100
    assert result["repeats"] == 3  # 1.4 + (8*3*3 - 2) * 1.1 = 78.4; four repeats would be 104.8
    assert "authlib-jws-none/H1/forward/r0" not in result["budget_censored"]


def test_gate_calibration_counts_reruns_and_can_stop(tmp_path, monkeypatch, capsys):
    runs = tmp_path / "runs" / "agent_verify" / "v1.1"
    attempt(runs, "authlib-jws-none/H1/forward/r0.invalid1", None)  # charged at the cap
    attempt(runs, "authlib-jws-none/H1/forward/r0", 0.5)
    (tmp_path / "gate.txt").write_text("authlib-jws-none/H1/forward/r0\n")
    monkeypatch.setattr(budget, "ROOT", tmp_path)
    args = Namespace(protocol="v1.1", cases=[ROOT / "fixtures/authlib-jws-none/case.yaml"],
                     gate=tmp_path / "gate.txt", label=LABEL, cap=3.0, ceiling=5.0,
                     buffer=0.10, repeats=5)
    budget.plan(args)
    result = json.loads((runs / "budget_plan.json").read_text())
    assert result["gate_costs_usd"] == {"authlib-jws-none/H1/forward/r0": 3.5}
    assert result["repeats"] == 0
    assert "STOP" in capsys.readouterr().out
