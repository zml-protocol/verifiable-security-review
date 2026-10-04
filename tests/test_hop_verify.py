import re
import sys
from itertools import pairwise
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "hop_verify"))

import verify

HV = ROOT / "experiments" / "hop_verify"


# ---- anchors ---------------------------------------------------------------------


def _ep(lo, hi, expr, file="f"):
    return {"file": file, "start_line": lo, "end_line": hi, "expression": expr}


def test_locate_normalizes_whitespace_across_lines():
    text = "a := 1\n\tx.Routes = append(\n\t\tx.Routes,\n\t\ty)\n"
    # a line break compares as one space, like any other whitespace run
    assert verify.locate(text, _ep(2, 4, "x.Routes  =  append( x.Routes,\n y)"), byte_columns=True) == (2, 2)
    assert verify.locate(text, _ep(2, 2, "x.Routes = append("), byte_columns=True) == (2, 2)


def test_locate_requires_exactly_one_occurrence_inside_the_span():
    text = "r = append(r, get)\nr = append(r, get)\n"
    assert verify.locate(text, _ep(2, 2, "append(r, get)"), byte_columns=True) == (2, 5)
    with pytest.raises(verify.AnchorError, match="2 times"):
        verify.locate(text, _ep(1, 2, "append(r, get)"), byte_columns=True)
    with pytest.raises(verify.AnchorError, match="0 times"):
        verify.locate(text, _ep(1, 1, "append(r, post)"), byte_columns=True)
    with pytest.raises(verify.AnchorError, match="outside"):
        verify.locate(text, _ep(2, 3, "r"), byte_columns=True)


def test_go_columns_count_bytes_python_columns_count_characters():
    text = 's := "é"; t := s\n'
    assert verify.locate(text, _ep(1, 1, "t := s"), byte_columns=True) == (1, 12)
    assert verify.locate(text, _ep(1, 1, "t := s"), byte_columns=False) == (1, 11)


# ---- judging ---------------------------------------------------------------------

SRC = {
    "flow.go": "package p\n\nfunc F() {\n\tok := S{\n\t\tCodes: []int{2},\n\t}\n\tok.Steps = append(ok.Steps, 1)\n}\n",
}
FIX = {"language": "go", "repo": "unused", "commits": {"base": "b", "head": "h"}}
ANALYSIS = {
    "status": "ok",
    "shapes": [["file", "flow.go", 0, 0, 0], ["definition", "flow.go", 4, 2, 6],
               ["keyed_field", "flow.go", 5, 3, 5], ["field_store", "flow.go", 7, 2, 7]],
    "rows": {"guard_property": [["flow.go", 5, 3, "flow.go", 7, 2]]},
}


@pytest.fixture
def sources(monkeypatch):
    monkeypatch.setattr(verify, "source", lambda fixture, rev, file: SRC.get(file))


def _hop(frm, to, relation="guard_property"):
    return {"id": "x", "fixture": "p", "revision": "base", "relation": relation, "from": frm, "to": to}


GUARD = _ep(5, 5, "Codes: []int{2}", "flow.go")
STORE = _ep(7, 7, "ok.Steps = append(ok.Steps, 1)", "flow.go")


def test_judge_states(sources):
    assert verify.judge(_hop(GUARD, STORE), FIX, ANALYSIS)["state"] == "VERIFIED"
    no_rows = {**ANALYSIS, "rows": {"guard_property": []}}
    assert verify.judge(_hop(GUARD, STORE), FIX, no_rows)["state"] == "UNVERIFIED"
    # reversed: a field store is no keyed field -> closed-world shape contradiction
    assert verify.judge(_hop(STORE, GUARD), FIX, ANALYSIS)["state"] == "CONTRADICTED"
    missing = _ep(7, 7, "ok.Steps = append(ok.Steps, 2)", "flow.go")
    assert verify.judge(_hop(GUARD, missing), FIX, ANALYSIS)["state"] == "ANCHOR_REJECTED"


def test_unextracted_file_or_failed_run_is_a_tool_failure_never_a_contradiction(sources):
    not_extracted = {**ANALYSIS, "shapes": [r for r in ANALYSIS["shapes"] if r[0] != "file"]}
    assert verify.judge(_hop(GUARD, STORE), FIX, not_extracted)["state"] == "TOOL_FAILURE"
    failed = {"status": "tool_failure", "stage": "database", "error": "boom"}
    assert verify.judge(_hop(GUARD, STORE), FIX, failed)["state"] == "TOOL_FAILURE"


def test_inside_role_matches_the_resolved_function_range(monkeypatch):
    src = {"a.py": "class A:\n    def f(self):\n        return 1\n\n\nx = self.c.f()\n"}
    monkeypatch.setattr(verify, "source", lambda fixture, rev, file: src.get(file))
    fix = {"language": "python", "repo": "unused", "commits": {"base": "b"}}
    call, body = _ep(6, 6, "self.c.f()", "a.py"), _ep(3, 3, "return 1", "a.py")
    analysis = {"status": "ok",
                "shapes": [["file", "a.py", 0, 0, 0], ["attribute_method_call", "a.py", 6, 5, 6],
                           ["function_body", "a.py", 2, 1, 3]],
                "rows": {"call_typed_attribute": [["a.py", 6, 5, "a.py", 2, 3]]}}
    hop = _hop(call, body, "call_typed_attribute")
    assert verify.judge(hop, fix, analysis)["state"] == "VERIFIED"
    analysis["rows"]["call_typed_attribute"] = [["a.py", 6, 5, "a.py", 8, 9]]
    assert verify.judge(hop, fix, analysis)["state"] == "UNVERIFIED"


# ---- scoring and routing -----------------------------------------------------------


def _states(pairs):
    return {hid: {"relation": rel, "state": st} for hid, rel, st in pairs}


def test_classes_and_the_two_unsafe_conditions():
    truth = {"t1": {"label": True}, "t2": {"label": True}, "f1": {"label": False, "kind": "shift"},
             "f2": {"label": False, "kind": "wrong_revision"}}
    states = _states([("t1", "r", "VERIFIED"), ("t2", "r", "UNVERIFIED"),
                      ("f1", "r", "UNVERIFIED"), ("f2", "r", "ANCHOR_REJECTED")])
    m = verify.score_states(states, truth)["relations"]["r"]
    assert m["class"] == "PARTIAL" and m["true_hop_coverage"] == 0.5
    assert m["false_hops"] == 1 and m["caught_by_anchor"] == 1 and m["false_verification_rate"] == 0
    assert m["verification_precision"] == 1.0
    states["f1"]["state"] = "VERIFIED"
    assert verify.score_states(states, truth)["relations"]["r"]["class"] == "UNSAFE"
    states["f1"]["state"], states["t2"]["state"] = "UNVERIFIED", "CONTRADICTED"
    assert verify.score_states(states, truth)["relations"]["r"]["class"] == "UNSAFE"
    states["t2"]["state"] = "TOOL_FAILURE"
    assert verify.score_states(states, truth)["relations"]["r"]["class"] == "INCONCLUSIVE_TOOL_FAILURE"
    states["t1"]["state"] = states["t2"]["state"] = "UNVERIFIED"
    assert verify.score_states(states, truth)["relations"]["r"]["class"] == "BLIND"


def _scored(classes):
    return {"relations": {name: {"class": c} for name, c in classes.items()}}


GAPS = ["registry_dispatch", "field_flow", "object_composition", "guard_property"]


def test_routing():
    ok = {"call_typed_attribute": "SUPPORTED", "registry_dispatch": "BLIND", "field_flow": "SUPPORTED",
          "object_composition": "PARTIAL", "guard_property": "BLIND"}
    r = verify.routing(_scored(ok), _scored(ok), GAPS)
    assert r["decision"] == "HYBRID_2_LIMITED_SCOPE"
    assert r["verifiable_in_hybrid_2"] == ["call_typed_attribute", "field_flow", "object_composition"]
    assert r["blind_spots"] == ["guard_property", "registry_dispatch"]
    # any UNSAFE, in calibration or evaluation, blocks Hybrid-2
    assert verify.routing(_scored({**ok, "guard_property": "UNSAFE"}), _scored(ok), GAPS)["decision"] == "NO_HYBRID_2"
    # a non-gap relation alone does not open Hybrid-2
    only_call = {**{g: "BLIND" for g in GAPS}, "call_typed_attribute": "SUPPORTED"}
    assert verify.routing(_scored(only_call), _scored(only_call), GAPS)["decision"] == "NO_NEW_CAPABILITY"
    tool = {**only_call, "field_flow": "INCONCLUSIVE_TOOL_FAILURE"}
    assert verify.routing(_scored(only_call), _scored(tool), GAPS)["decision"] == "INCONCLUSIVE_TOOL_FAILURE"


def test_a_relation_whose_calibration_failed_cannot_enter_hybrid_2():
    cal = {"call_typed_attribute": "SUPPORTED", "registry_dispatch": "BLIND",
           "field_flow": "INCONCLUSIVE_TOOL_FAILURE", "object_composition": "BLIND",
           "guard_property": "SUPPORTED"}
    ev = {**cal, "field_flow": "SUPPORTED"}
    r = verify.routing(_scored(cal), _scored(ev), GAPS)
    assert r["decision"] == "HYBRID_2_LIMITED_SCOPE"
    assert r["verifiable_in_hybrid_2"] == ["call_typed_attribute", "guard_property"]
    assert "field_flow" in r["blind_spots"] and r["inconclusive"] == ["field_flow"]


def test_only_covered_gap_lost_to_a_calibration_failure_is_inconclusive():
    cal = {**{g: "BLIND" for g in GAPS}, "call_typed_attribute": "SUPPORTED",
           "field_flow": "INCONCLUSIVE_TOOL_FAILURE"}
    ev = {**{g: "BLIND" for g in GAPS}, "call_typed_attribute": "SUPPORTED", "field_flow": "SUPPORTED"}
    r = verify.routing(_scored(cal), _scored(ev), GAPS)
    assert r["decision"] == "INCONCLUSIVE_TOOL_FAILURE" and r["verifiable_in_hybrid_2"] == []
    # a relation with no calibration result at all is treated the same way
    r = verify.routing(_scored({k: v for k, v in cal.items() if k != "field_flow"}), _scored(ev), GAPS)
    assert r["decision"] == "INCONCLUSIVE_TOOL_FAILURE"


# ---- frozen inputs -----------------------------------------------------------------


def _have(set_name):
    s = verify.hop_set(set_name)
    return all((ROOT / f["repo"]).exists() for f in s["fixtures"].values())


@pytest.mark.parametrize("set_name", verify.SETS)
def test_sets_are_clean(set_name):
    if not _have(set_name):
        pytest.skip("fixture repositories not built")
    assert verify.check_set(set_name) == []


@pytest.mark.parametrize("set_name,prefix", [("cal", "c"), ("eval", "e")])
def test_held_out_hop_ids_are_opaque(set_name, prefix):
    ids = [h["id"] for h in verify.hop_set(set_name)["hops"]]
    assert all(re.fullmatch(rf"{prefix}\d\d", i) for i in ids) and len(set(ids)) == len(ids)


def _span(lines):
    lo, _, hi = str(lines).partition("-")
    return int(lo), int(hi or lo)


def _golden_chains(fixture_id, revision, spec):
    """§10.3: every path-fact evidence set, in order, plus the Spike P sink when that sink is
    itself a golden location of a hypothesis carrying the path fact."""
    fixture = spec["fixtures"][fixture_id]
    golden = yaml.safe_load((ROOT / "fixtures" / fixture_id / "golden.yaml").read_text())
    sink = fixture["endpoints"][revision]["sink"]
    chains = set()
    for hyp in golden["hypotheses"].values():
        facts = [f for f in hyp["facts"] if f["revision"] == revision]
        path = [f for f in facts if f["id"] == f"{revision}-{fixture['path_fact']}"]
        tail = [(loc["path"], *_span(loc["lines"])) for f in facts for es in f["evidence_sets"]
                for loc in es if loc["path"] == sink["file"]
                and _span(loc["lines"])[0] <= sink["line"] <= _span(loc["lines"])[1]]
        for f in path:
            for es in f["evidence_sets"]:
                chains.add(tuple([(loc["path"], *_span(loc["lines"])) for loc in es] + tail[:1]))
    return chains


def test_true_eval_hops_are_exactly_the_split_golden_chains():
    s, truth = verify.hop_set("eval"), verify.truth_of("eval")["truth"]
    spec = yaml.safe_load((ROOT / "experiments/provider_reach/endpoints.yaml").read_text())
    for fid in s["fixtures"]:
        for rev in ("base", "head"):
            locs = spec["fixtures"][fid]["locations"]
            locs = locs if isinstance(locs, list) else locs[rev]
            labels = {(loc["file"], *_span(loc["lines"])): loc["relation"] for loc in locs}
            expected = {(a, b, labels[a]) for chain in _golden_chains(fid, rev, spec)
                        for a, b in pairwise(chain)}
            actual = {((h["from"]["file"], h["from"]["start_line"], h["from"]["end_line"]),
                       (h["to"]["file"], h["to"]["start_line"], h["to"]["end_line"]), h["relation"])
                      for h in s["hops"] if h["fixture"] == fid and h["revision"] == rev
                      and truth[h["id"]]["label"]}
            assert expected and actual == expected, (fid, rev)


FIXTURE_WORDS = ["authlib", "jws", "jwe", "jwt", "verify", "algorithm", "caddy", "reverseproxy",
                 "goodResponseHandler", "HandleResponse", "rpHandler", "StatusCode", "filebrowser",
                 "nameInArchive", "archive", "Routes", "deserialize", "none"]


def test_verifier_queries_name_no_fixture_symbol():
    for q in sorted((HV / "queries").rglob("*.ql*")):
        text = re.sub(r"secreview/[\w-]+", "", q.read_text())
        hits = [w for w in FIXTURE_WORDS if re.search(rf"\b{re.escape(w)}\b", text, re.IGNORECASE)]
        assert not hits, (q.name, hits)


def test_every_relation_has_a_verifier_and_only_shape_checks_contradict():
    rel = verify.relations()
    assert set(rel["gaps"]) < set(rel["relations"])
    for name, spec in rel["relations"].items():
        assert (HV / "queries" / spec["language"] / spec["verifier"]).is_file(), name
        assert spec["states"] == ["VERIFIED", "UNVERIFIED", "CONTRADICTED"]
        assert spec["from"]["role"] == "node" and spec["to"]["role"] in ("node", "inside")
