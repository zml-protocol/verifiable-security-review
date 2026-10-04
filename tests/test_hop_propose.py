import asyncio
import gzip
import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest
import yaml
from mcp import Client

ROOT = Path(__file__).resolve().parents[1]
HP = ROOT / "experiments" / "hop_propose"
sys.path.insert(0, str(HP))

import feedback
import propose_run as R
import propose_score as S

from spike import hops as hoplib
from spike.hop_mcp_server import build_server
from spike.hop_session import HopSession
from spike.session import ToolInputError

needs_repos = pytest.mark.skipif(
    not all((ROOT / p).exists() for p in (".cache/repos/authlib.git", ".cache/repos/caddy.git",
                                           ".cache/repos/filebrowser.git", ".cache/fixtures/hopdev-go")),
    reason="fixture repositories not built")


# ---- frozen verifier output ---------------------------------------------------------------


def test_frozen_analyses_are_intact_and_complete():
    assert S.frozen_ok()
    for name in json.loads((R.FROZEN / "manifest.json").read_text())["files"]:
        data = json.loads(gzip.decompress((R.FROZEN / name).read_bytes()))
        wanted = {n for n, r in R.RELATIONS.items() if r["language"] == data["language"]}
        assert set(data["rows"]) == wanted, name  # every relation of the language, not a subset
        assert any(r[0] == "file" for r in data["shapes"])


@needs_repos
def test_hop_core_reproduces_the_committed_p_hybrid_1_states():
    hv = ROOT / "experiments" / "hop_verify"
    hop_set = yaml.safe_load((hv / "sets" / "eval.yaml").read_text())
    committed = json.loads((ROOT / "results" / "p-hybrid-1-eval.json").read_text())
    states = {h: m["state"] for r in committed["relations"].values() for h, m in r["hops"].items()}
    matchers = {}
    for hop in hop_set["hops"]:
        m = matchers.setdefault(hop["fixture"], S.Matcher(hop["fixture"], pilot=False))
        canonical = {k: hop[k] for k in ("revision", "relation", "from", "to")}
        try:
            res = m.resolve(canonical)
            got = hoplib.verdict(canonical, res, R.RELATIONS, m.analysis[hop["revision"]])
        except hoplib.HopError as e:
            got = {"anchor": "ANCHOR_REJECTED", "shape": "CONTRADICTED"}[e.code]
        assert got == states[hop["id"]], hop["id"]


@needs_repos
def test_every_golden_hop_matches_itself_verified_and_nothing_else():
    for fixture in R.CASES["eval"]:
        m = S.Matcher(fixture, pilot=False)
        sub = m.submission([{"id": g["id"], **{k: g[k] for k in ("revision", "relation", "from", "to")}}
                            for g in m.golden])
        assert sub["verified_coverage"] == 1.0 and sub["located_coverage"] == 1.0
        for row in sub["hops"]:
            assert row["golden"] == [row["id"]] and row["state"] == "VERIFIED" and row["unit"] is None


@needs_repos
def test_matching_rule_inside_role_uses_the_callee_function_not_the_span():
    m = S.Matcher("authlib-jws-none", pilot=False)
    g = next(g for g in m.golden if g["relation"] == "call_typed_attribute" and g["revision"] == "base")
    # `to` on the callee's def line instead of the golden 106-109 span: same callee, same claim
    moved = {**{k: g[k] for k in ("revision", "relation", "from")},
             "to": {"file": g["to"]["file"], "start_line": 77, "end_line": 77,
                    "expression": "def deserialize_compact(self, s, key, decode=None):"}}
    sub = m.submission([{"id": "x", **moved}])
    assert sub["hops"][0]["golden"] == [g["id"]] and sub["hops"][0]["state"] == "VERIFIED"
    # the same place typed with another relation is located, not a typed match
    mid_call = {**moved, "from": {**g["from"], "expression": "deserialize_compact(s, load_key"}}
    with pytest.raises(hoplib.HopError, match="must name"):  # not where the call starts
        m.resolve(mid_call)
    retyped = {**moved, "relation": "registry_dispatch"}  # a.b.m(...) is also an r.m(...)
    sub = m.submission([{"id": "y", **retyped}])
    assert sub["hops"][0]["golden"] == [] and sub["hops"][0]["located"] == [g["id"]]
    assert sub["verified_coverage"] == 0 and sub["located_coverage"] == 0.25


# ---- the session --------------------------------------------------------------------------


GOOD = {"revision": "base", "relation": "field_flow",
        "from": {"file": "flow.go", "start_line": 27, "end_line": 27,
                 "expression": "label := strings.TrimPrefix(raw, prefix)"},
        "to": {"file": "flow.go", "start_line": 31, "end_line": 31, "expression": "Label: label"}}


def _session(tmp_path, phase="initial", snapshot=None):
    d = tmp_path / phase
    return HopSession(R.session_config("hopdev-go", True, 0, d, phase, snapshot)), d


@needs_repos
def test_submission_locks_once_all_valid_deduplicated_and_capped(tmp_path):
    s, d = _session(tmp_path)
    shifted = {**GOOD, "from": {**GOOD["from"], "expression": "strings.TrimPrefix(raw, prefix)"}}
    assert s.call("validate_hop", hop=GOOD)["ok"]
    assert "[shape]" in s.call("validate_hop", hop=shifted)["problem"]
    with pytest.raises(ToolInputError, match="nothing was locked"):
        s.call("submit_hops", hops=[GOOD, shifted])
    assert json.loads((d / "state.json").read_text())["initial"] is None
    many = [{**GOOD, "to": {**GOOD["to"], "expression": "Label: label", "end_line": 31}}] * 20
    locked = s.call("submit_hops", hops=many)  # 20 copies are one distinct hop
    assert locked["locked"] == "initial" and locked["hops"].count("field_flow") == 1
    with pytest.raises(ToolInputError, match="already locked"):
        s.call("submit_hops", hops=[GOOD])


@needs_repos
def test_cap_counts_distinct_hops(tmp_path):
    s, _ = _session(tmp_path)
    s.hop_config.max_hops = 1
    other = {**GOOD, "from": {**GOOD["from"], "start_line": 28, "end_line": 28,
                              "expression": "label = filepath.ToSlash(label)"}}
    with pytest.raises(ToolInputError, match="too_many_hops|at most"):
        s.call("submit_hops", hops=[GOOD, other])


@needs_repos
def test_final_phase_restores_the_snapshot_and_submits_once(tmp_path):
    s, d = _session(tmp_path)
    s.call("submit_hops", hops=[GOOD])
    snap = tmp_path / "snap.json"
    snap.write_text((d / "state.json").read_text())
    f, fd = _session(tmp_path, "final", snap)
    assert "h1  base  field_flow" in f.call("get_task")["initial_hops"]
    assert f.initial == json.loads(snap.read_text())["initial"]
    f.call("submit_hops", hops=[])
    state = json.loads((fd / "state.json").read_text())
    assert state["final"] == [] and state["initial"] == f.initial
    with pytest.raises(ToolInputError, match="already locked"):
        f.call("submit_hops", hops=[GOOD])


@needs_repos
def test_unsupported_hops_check_anchors_only(tmp_path):
    s, _ = _session(tmp_path)
    loose = {**GOOD, "relation": "unsupported",
             "from": {**GOOD["from"], "expression": "strings.TrimPrefix(raw, prefix)"}}
    assert s.call("validate_hop", hop=loose)["ok"]
    wrong_lang = {**GOOD, "relation": "registry_dispatch"}
    assert "[schema]" in s.call("validate_hop", hop=wrong_lang)["problem"]


@needs_repos
def test_hop_tools_round_trip_over_mcp_with_the_from_key(tmp_path):
    s, _ = _session(tmp_path)

    async def go():
        async with Client(build_server(s)) as client:
            names = {t.name for t in (await client.list_tools()).tools}
            assert {"validate_hop", "submit_hops", "read_code"} <= names
            assert not names & {"submit_observation", "finish"}
            ok = await client.call_tool("validate_hop", {"hop": GOOD})
            assert '"ok": true' in ok.content[0].text
            task = (await client.call_tool("get_task", {})).content[0].text
            assert "hop_format:" in task and "verifier" not in task.lower()

    asyncio.run(go())


# ---- feedback, commands, order ----------------------------------------------------------


def test_treatment_message_is_control_plus_the_whitelisted_block():
    rows = [("h1", "VERIFIED"), ("h2", "UNVERIFIED")]
    control, treatment = feedback.message("control", rows), feedback.message("treatment", rows)
    assert treatment == control + "\n" + feedback.block(rows)
    assert "verifier" not in control.lower()
    body = feedback.block(rows).splitlines()
    assert body[0] == feedback.HEADER and body[1:3] == ["h1  VERIFIED", "h2  UNVERIFIED"]
    assert body[4:] == [f"{k}: {v}" for k, v in feedback.LEGEND.items()]
    with pytest.raises(ValueError):
        feedback.block([("h1", "CONTRADICTED")])  # nothing outside the whitelist


def test_parent_persists_its_session_and_children_fork_it():
    args = Namespace(model="m", effort="high", budget_usd=3.0)
    parent = R.claude_cmd("p", Path("mcp.json"), args, session_id="S", resume=None)
    child = R.claude_cmd("c", Path("mcp.json"), args, session_id=None, resume="S")
    assert "--no-session-persistence" not in parent and parent[3:5] == ["--session-id", "S"]
    assert child[3:6] == ["--resume", "S", "--fork-session"]
    assert "--strict-mcp-config" in child and child[child.index("--tools") + 1] == ""


def test_order_is_seeded_repeat_major_and_complete(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for out in (a, b):
        R.order(Namespace(out=out))
    assert a.read_text() == b.read_text() == (HP / "order.txt").read_text()
    blocks = R.read_order(a)
    assert sorted(blocks) == sorted((f, r) for f in R.CASES["eval"] for r in range(R.REPEATS))
    assert [r for _, r in blocks] == sorted(r for _, r in blocks)


# ---- scoring rules ----------------------------------------------------------------------


def _pair(fixture, gain_t, gain_c, n=2):
    sub = lambda cov: {"verified_coverage": cov, "located_coverage": cov, "n": n, "verified": n,
                       "contradicted": 0, "supported": n, "unsupported": 0, "hops": [],
                       "verified_golden": [], "located_golden": []}
    return {"block": f"{fixture}/rX", "fixture": fixture, "repeat": 0, "initial": sub(0.0),
            "control": sub(gain_c), "treatment": sub(gain_t), "gain": gain_t - gain_c}


HUMAN = {"type": "human", "name": "A. Reviewer",
         "attestation": {"independent": True, "saw_arms": False, "saw_verdicts": False}}


def _summary(pairs, monkeypatch, labels=None):
    review = None if labels is None else {"reviewer": HUMAN, "labels": labels}
    monkeypatch.setattr(S, "load_review", lambda which, pilot: review if which == "primary" else None)
    return S.summarize(pairs, [], {"isolation": {}, "context_leak": {}, "foreign_tools": {},
                                   "harness_errors": 0}, pilot=False)


def test_rates_with_empty_denominators_are_zero():
    assert S.rate(0, 0) == 0.0
    assert S.validity_share([], {})["false_share"] == 0.0


def test_verdict_order(monkeypatch):
    fixtures = sorted(R.CASES["eval"])
    good = [_pair(f, 0.5, 0.25) for f in fixtures for _ in range(5)]
    assert _summary(good, monkeypatch)["verdict"] == "REVIEW_PENDING"  # no primary labels yet
    r = _summary(good, monkeypatch, labels={})
    assert r["verdict"] == "SUCCESS" and all(r["criteria"].values())
    assert r["primary_review_kind"] == "human"
    thin = [p for p in good if p["fixture"] != fixtures[0]][:-1]
    assert _summary(thin, monkeypatch, labels={})["verdict"] == "INCONCLUSIVE_INFRA"
    flat = [_pair(f, 0.25, 0.25) for f in fixtures for _ in range(5)]
    r = _summary(flat, monkeypatch, labels={})
    assert r["verdict"] == "FAIL" and not r["criteria"]["mean_gain"]
    assert not r["criteria"]["caddy_pair_treatment_above"]  # equal is not above


def test_three_pairs_below_fail_even_with_a_large_mean(monkeypatch):
    fixtures = sorted(R.CASES["eval"])
    pairs = [_pair(f, 1.0, 0.0) for f in fixtures for _ in range(4)]
    pairs += [_pair(f, 0.0, 0.25) for f in fixtures]
    r = _summary(pairs, monkeypatch, labels={})
    assert r["pairs_treatment_below"] == 3 and not r["criteria"]["few_pairs_treatment_below"]
    assert r["verdict"] == "FAIL"


@needs_repos
def test_a_locked_hop_the_scorer_rejects_is_a_harness_violation(monkeypatch):
    m = S.Matcher("hopdev-go", pilot=True)
    bad = {"id": "f1", **GOOD, "from": {**GOOD["from"], "expression": "strings.TrimPrefix(raw, prefix)"}}
    sub = m.submission([bad])
    assert sub["rejected"] == ["f1"] and sub["contradicted"] == 1
    fixtures = sorted(R.CASES["eval"])
    pairs = [_pair(f, 0.5, 0.25) for f in fixtures for _ in range(5)]
    monkeypatch.setattr(S, "load_review", lambda which, pilot: {"reviewer": HUMAN, "labels": {}}
                        if which == "primary" else None)
    r = S.summarize(pairs, [], {"isolation": {}, "context_leak": {}, "foreign_tools": {},
                                "harness_errors": 0,
                                "locked_hop_rejected": {"x/r0/treatment": ["f1"]}}, pilot=False)
    assert r["verdict"] == "HARNESS_INVALID" and "contradiction_guard" not in r["criteria"]


def test_labels_need_a_reviewer_and_the_attestation():
    ok = {"reviewer": {"type": "human", "name": "A. Reviewer",
                       "attestation": {"independent": True, "saw_arms": False, "saw_verdicts": False}},
          "labels": {}}
    assert S.reviewer_of(ok) == ok["reviewer"]
    for broken in ({"labels": {}},
                   {**ok, "reviewer": {**ok["reviewer"], "name": " "}},
                   {**ok, "reviewer": {**ok["reviewer"], "type": "robot"}},
                   {**ok, "reviewer": {**ok["reviewer"], "attestation": {"independent": True}}},
                   {**ok, "reviewer": {**ok["reviewer"], "attestation": {
                       "independent": True, "saw_arms": True, "saw_verdicts": False}}}):
        assert S.reviewer_of(broken) is None
