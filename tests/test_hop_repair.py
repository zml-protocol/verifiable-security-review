import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HR = ROOT / "experiments" / "hop_repair"
sys.path.insert(0, str(HR))

import messages
import power
import repair_run as RR
import repair_score as RS

needs_repos = pytest.mark.skipif(
    not (ROOT / ".cache/repos/caddy.git").exists(), reason="fixture repositories not built")


# ---- what each arm sees -------------------------------------------------------------------


def test_treatment_is_control_plus_exactly_one_sentence():
    control, treatment = messages.message("control"), messages.message("treatment")
    assert control == (ROOT / "experiments/hop_propose/revision.md").read_text()
    assert treatment == control + "\n" + messages.BIT + "\n"
    assert messages.BIT == ("The currently submitted evidence is not complete under the "
                            "verification contract.")
    for word in ("hop", "relation", "entry", "guard", "qualifier", "node", "line", "missing"):
        assert word not in messages.BIT.lower()  # nothing about where or what


def test_contract_statements_are_the_frozen_golden_statements():
    contract = yaml.safe_load((HR / "contract.yaml").read_text())
    facts = {"authlib-jws-none": "decode-reaches-verify",
             "caddy-forward-auth": "copy-routes-run-on-2xx",
             "filebrowser-archive-backslash": "stored-path-becomes-entry"}
    for fixture, fact in facts.items():
        golden = yaml.safe_load((ROOT / "fixtures" / fixture / "golden.yaml").read_text())
        statements = {f["statement"] for f in golden["hypotheses"]["H1"]["facts"]
                      if f["id"].endswith(fact)}
        assert statements == {contract["statements"][fixture]}, fixture
    assert not re.search(r"\d", contract["generic"])  # no line numbers, no counts


@needs_repos
def test_contract_reaches_get_task_only_in_section_13(tmp_path):
    from spike.hop_session import HopSession

    cfg = RR.config("caddy-forward-auth", False, 0, tmp_path / "a", "initial", None)
    task = HopSession(cfg).call("get_task")
    assert task["verification_contract"].endswith(yaml.safe_load(
        (HR / "contract.yaml").read_text())["statements"]["caddy-forward-auth"])
    plain = RR.P.session_config("caddy-forward-auth", False, 0, tmp_path / "b", "initial", None)
    assert "verification_contract" not in HopSession(plain).call("get_task")  # §11/§12 unchanged


# ---- sampling and outcomes ----------------------------------------------------------------


def _counts(valid, full, pairs):
    return {"valid_initials": valid, "initially_full": full, "eligible": valid - full,
            "complete_pairs": pairs}


def test_stopping_rule_reads_only_pre_treatment_counts():
    caddy, fb, authlib = RS.PRIMARY[0], RS.PRIMARY[1], RS.SANITY[0]
    assert not RS.done(caddy, _counts(20, 9, RS.K_ELIGIBLE - 1), False)
    assert RS.done(caddy, _counts(20, 8, RS.K_ELIGIBLE), False)
    assert RS.done(fb, _counts(RS.M_INITIALS, 29, 1), False)  # cap: opportunity not met
    assert not RS.done(authlib, _counts(RS.N_SANITY - 1, 4, 0), False)
    assert RS.done(authlib, _counts(RS.N_SANITY, 5, 0), False)


def test_outcomes():
    assert RS.outcome(False, True) == "T_only" and RS.outcome(True, False) == "C_only"
    assert RS.outcome(True, True) == "Both" and RS.outcome(False, False) == "Neither"


def _pf(t, c, met=True, reached=True):
    return {"outcomes": {"T_only": t, "C_only": c, "Both": 0, "Neither": 0},
            "opportunity_met": met, "reached_target": reached}


SANE = {RS.SANITY[0]: _pf(0, 0)}


def test_verdict_order_and_rule():
    caddy, fb = RS.PRIMARY
    ok = {caddy: _pf(4, 0), fb: _pf(3, 1), **SANE}
    assert RS.decide(True, False, ok)[0] == "SUCCESS"  # pooled 7 vs 1: p = 0.035
    assert RS.decide(False, False, ok)[0] == "HARNESS_INVALID"
    assert RS.decide(True, False, {caddy: _pf(4, 0), fb: _pf(3, 1, met=False), **SANE})[0] == \
        "INCONCLUSIVE_OPPORTUNITY"  # cap reached, target not
    assert RS.decide(True, False, {caddy: _pf(4, 0), fb: _pf(3, 1, met=False, reached=False),
                                   **SANE})[0] == "RUN_INCOMPLETE"  # neither: still running
    assert RS.decide(True, False, ok, config_mismatch=True)[0] == "PROTOCOL_INVALID"
    one_sided = {caddy: _pf(7, 0), fb: _pf(0, 1), **SANE}  # pooled p = 0.035 but File Browser goes backwards
    status, criteria, _ = RS.decide(True, False, one_sided)
    assert status == "FAIL" and criteria["pooled_significant"]
    assert RS.decide(True, False, {caddy: _pf(2, 0), fb: _pf(2, 0), **SANE})[0] == "FAIL"  # 4 vs 0: p = 0.0625


def test_power_table_basics():
    assert power.sign_p(5, 0) <= power.ALPHA < power.sign_p(4, 0)
    assert power.sign_p(0, 0) == 1.0
    assert power.power(RS.K_ELIGIBLE, 0.10, 0.10) < power.ALPHA  # conservative under the null


# ---- the frozen execution configuration (§13.1) ------------------------------------------


@pytest.mark.parametrize("change", [{"model": "claude-opus-5"}, {"effort": "medium"},
                                    {"budget_usd": 5.0}, {"timeout": 600}])
def test_a_formal_run_with_another_configuration_never_starts(change, monkeypatch):
    from argparse import Namespace

    monkeypatch.setattr(RR.C, "gate", list)
    monkeypatch.setattr(RR.C, "rows_problems", lambda targets: [])
    monkeypatch.setattr(RR, "cli_version", lambda: RS.FORMAL_SERVED["claude_code_version"])
    launched = []
    monkeypatch.setattr(RR, "run_block", lambda *a: launched.append(a) or [])
    args = {"pilot": False, "allow_dirty": True, "force_fork": False, "model": "claude-sonnet-5",
            "effort": "high", "budget_usd": 3.0, "timeout": 1200, **change}
    with pytest.raises(SystemExit, match="frozen execution configuration"):
        RR.run(Namespace(**args))
    assert launched == []


def test_another_cli_version_never_starts(monkeypatch):
    from argparse import Namespace

    monkeypatch.setattr(RR, "cli_version", lambda: "2.1.300")
    args = Namespace(model="claude-sonnet-5", effort="high", budget_usd=3.0, timeout=1200)
    assert RR.formal_config_problems(args) == ["claude CLI '2.1.300' (frozen '2.1.280')"]


def test_the_scorer_rejects_a_run_outside_the_frozen_configuration(tmp_path):
    import json

    def run_dir(meta, served):
        d = tmp_path / f"r{len(list(tmp_path.iterdir()))}"
        d.mkdir()
        (d / "meta.json").write_text(json.dumps(meta))
        (d / "agent.jsonl").write_text(json.dumps({"type": "system", "subtype": "init", **served}))
        return d

    good_meta = {**RS.FORMAL}
    assert RS.config_problems(run_dir(good_meta, RS.FORMAL_SERVED)) == []
    assert RS.config_problems(run_dir({**good_meta, "effort": "max"}, RS.FORMAL_SERVED)) == ["effort='max'"]
    forged = run_dir(good_meta, {**RS.FORMAL_SERVED, "model": "claude-opus-5"})  # meta says sonnet
    assert RS.config_problems(forged) == ["served model='claude-opus-5'"]
