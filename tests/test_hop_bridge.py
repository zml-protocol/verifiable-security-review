import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HB = ROOT / "experiments" / "hop_bridge"
sys.path.insert(0, str(HB))

import bridge as B

from spike import hops as hoplib

needs_repos = pytest.mark.skipif(
    not all((ROOT / p).exists() for p in (".cache/repos/authlib.git", ".cache/repos/filebrowser.git",
                                           ".cache/repos/caddy.git", ".cache/fixtures/bridgedev-go")),
    reason="fixture repositories not built")


def test_every_bridge_relation_has_a_verifier_and_node_roles():
    for lang, rels in B.BRIDGE["relations"].items():
        for name, spec in rels.items():
            assert (HB / "queries" / lang / spec["verifier"]).is_file(), name
            assert spec["from"]["role"] == spec["to"]["role"] == "node"
        assert (HB / "queries" / lang / B.BRIDGE["shapes"][lang]).is_file()
    # the bridge relations never shadow a frozen P-Hybrid-1 relation
    assert not (set(B.BRIDGE["relations"]["go"]) | set(B.BRIDGE["relations"]["python"])) & set(B.P1)


FIXTURE_WORDS = ["authlib", "caddy", "filebrowser", "getFiles", "nameInArchive", "filenames",
                 "fname", "rawDirHandler", "decode", "to_bytes", "deserialize", "handler"]


def test_bridge_queries_name_no_fixture_symbol():
    for q in sorted((HB / "queries").rglob("*.ql*")):
        text = re.sub(r"secreview/[\w-]+", "", q.read_text())
        assert not [w for w in FIXTURE_WORDS if re.search(rf"\b{w}\b", text)], q.name


@needs_repos
@pytest.mark.parametrize("set_name", B.SETS)
def test_sets_are_clean(set_name):
    assert B.check_set(set_name) == []


def test_entry_anchors_are_the_frozen_spike_p_sources():
    ends = yaml.safe_load((ROOT / "experiments/provider_reach/endpoints.yaml").read_text())
    anchors = B.entry_anchors()
    for fid, revs in anchors.items():
        for rev, node in revs.items():
            src = ends["fixtures"][fid]["endpoints"][rev]["source"]
            assert (node[1], node[2]) == (src["file"], src["line"]), (fid, rev)


@needs_repos
def test_true_bridge_hops_join_from_the_entry_to_the_section_12_entry():
    s, truth = B.hop_set("current"), B.truth_of("current")["truth"]
    local = yaml.safe_load((ROOT / "experiments/hop_chain/anchors.yaml").read_text())
    anchors = B.entry_anchors()
    for fid, fixture in s["fixtures"].items():
        for rev in ("base", "head"):
            true = [h for h in s["hops"] if h["fixture"] == fid and h["revision"] == rev
                    and truth[h["id"]]["label"]]

            def at(ep, fixture=fixture, rev=rev):
                text = B.verify.source(fixture, rev, ep["file"])
                return ("node", ep["file"], *hoplib.locate(text, ep, fixture["language"] == "go"))

            node, chain = tuple(anchors[fid][rev]), []
            while node != tuple(local[fid][rev]["entry"]):
                step = [h for h in true if at(h["from"]) == node]
                assert len(step) == 1, (fid, rev, node)
                chain.append(step[0]["id"])
                node = at(step[0]["to"])
            assert len(chain) == len(true), (fid, rev)  # every true hop is on the chain


@needs_repos
def test_the_frozen_golden_local_hops_close_every_section_12_chain():
    """§14.4: the local part is already closed, so any gap the check finds is in the bridge."""
    ev, ev_truth = B.verify.hop_set("eval"), B.verify.truth_of("eval")["truth"]
    local12 = yaml.safe_load((ROOT / "experiments/hop_chain/anchors.yaml").read_text())
    for fid, fixture in B.hop_set("current")["fixtures"].items():
        rels = {n: r for n, r in B.P1.items() if r["language"] == fixture["language"]}
        for rev in ("base", "head"):
            frozen = json.loads(B.frozen_p1(fid, rev))
            analysis = {"status": "ok", "shapes": frozen["shapes"], "rows": frozen["rows"]}
            local = [h for h in ev["hops"] if h["fixture"] == fid and h["revision"] == rev
                     and ev_truth[h["id"]]["label"]]
            edges = B.verified_edges(local, fixture, rels, analysis)
            assert len(edges) == len(local), (fid, rev)
            a12 = local12[fid][rev]
            assert B.classify(edges, fid, rev, fixture, tuple(a12["entry"]), a12)["class"] == "FULL_CHAIN"


def _scored(classes):
    return {"verifiers": {n: {"class": c} for n, c in classes.items()}}


CAL_OK = {"codeql/go/def_use": "SUPPORTED", "codeql/go/argument_binding": "PARTIAL",
          "codeql/go/range_element": "SUPPORTED", "codeql/python/def_use": "SUPPORTED"}
CUR_OK = {**CAL_OK, "codeql/go/object_composition": "SUPPORTED"}
CLOSED = {"a/base": {"class": "FULL_CHAIN"}, "a/head": {"class": "FULL_CHAIN"}}


def test_bridge_verifiers_are_scored_per_language():
    assert B.BRIDGE_VERIFIERS == sorted(CAL_OK)
    s = {"fixtures": {"g": {"language": "go"}, "p": {"language": "python"}}}
    states = {"x": {"relation": "def_use", "fixture": "g", "state": "VERIFIED"},
              "y": {"relation": "def_use", "fixture": "p", "state": "UNVERIFIED"}}
    truth = {"x": {"label": True}, "y": {"label": True}}
    out = B.scored(states, s, truth)
    per = out["verifiers"]
    assert per["codeql/go/def_use"]["class"] == "SUPPORTED"
    assert per["codeql/python/def_use"]["class"] == "BLIND"
    assert out["verifier_queries"] == {"codeql/go/def_use": "experiments/hop_bridge/queries/go/DefUse.ql",
                                       "codeql/python/def_use": "experiments/hop_bridge/queries/python/DefUse.ql"}
    # merged, Python's blind def_use hides inside a PARTIAL: report only, never routed on
    assert out["report_only_by_relation"]["def_use"]["class"] == "PARTIAL"
    cur = B.scored(states, s, truth)
    r = B.routing(out, cur, CLOSED)
    assert r["decision"] == "CALIBRATION_BLIND"
    # Python is blind; Go's hits do not cover for it (the toy lacks the other two verifiers too)
    assert "codeql/python/def_use" in r["calibration_blind"]
    assert "codeql/go/def_use" not in r["calibration_blind"]
    assert "def_use" not in r["classes"]


def test_every_preregistered_verifier_is_required_on_cal():
    """The required set comes from relations.yaml, not from the keys a result happens to hold."""
    assert B.BRIDGE_VERIFIERS == sorted(B.verifier_key(lang, n) for lang in ("go", "python")
                                        for n in B.BRIDGE["relations"][lang])
    for k in B.BRIDGE_VERIFIERS:
        assert (ROOT / B.verifier_query(k)).is_file()
    assert B.verifier_query("codeql/go/object_composition") == \
        "experiments/hop_verify/queries/go/ObjectComposition.ql"
    assert B.routing(_scored({}), _scored(CUR_OK), CLOSED)["calibration_blind"] == B.BRIDGE_VERIFIERS


def test_routing():
    assert B.routing(_scored(CAL_OK), _scored(CUR_OK), CLOSED)["decision"] == "LOOP_CLOSED"
    assert B.routing(_scored({**CAL_OK, "codeql/go/def_use": "UNSAFE"}), _scored(CUR_OK), CLOSED)[
        "decision"] == "UNSAFE"
    frozen_unsafe = _scored({**CUR_OK, "codeql/go/object_composition": "UNSAFE"})
    assert B.routing(_scored(CAL_OK), frozen_unsafe, CLOSED)["decision"] == "UNSAFE"
    tool = _scored({**CAL_OK, "codeql/go/range_element": "INCONCLUSIVE_TOOL_FAILURE"})
    assert B.routing(tool, _scored(CUR_OK), CLOSED)["decision"] == "INCONCLUSIVE_TOOL_FAILURE"
    assert B.routing(tool, frozen_unsafe, CLOSED)["decision"] == "UNSAFE"  # UNSAFE wins
    gap = {**CLOSED, "a/head": {"class": "ENTRY_GAP"}}
    r = B.routing(_scored(CAL_OK), _scored(CUR_OK), gap)
    assert r["decision"] == "CAPABILITY_GAPS" and r["gaps"] == {"a/head": "ENTRY_GAP"}


def test_a_blind_calibration_never_closes_the_loop():
    """Codex r1: a verifier that accepts only the known current hop is not a calibrated capability."""
    blind_go = _scored({**CAL_OK, "codeql/go/def_use": "BLIND"})
    r = B.routing(blind_go, _scored(CUR_OK), CLOSED)
    assert r["decision"] == "CALIBRATION_BLIND" and r["calibration_blind"] == ["codeql/go/def_use"]
    blind_py = _scored({**CAL_OK, "codeql/python/def_use": "BLIND"})
    assert B.routing(blind_py, _scored(CUR_OK), CLOSED)["decision"] == "CALIBRATION_BLIND"
    missing = {k: v for k, v in CAL_OK.items() if k != "codeql/go/range_element"}
    assert B.routing(_scored(missing), _scored(CUR_OK), CLOSED)["decision"] == "CALIBRATION_BLIND"
    # a blind calibration outranks a chain gap; PARTIAL (argument_binding's known blind spots) closes
    gap = {**CLOSED, "a/head": {"class": "ENTRY_GAP"}}
    assert B.routing(blind_go, _scored(CUR_OK), gap)["decision"] == "CALIBRATION_BLIND"
    partial = _scored({**CAL_OK, "codeql/go/argument_binding": "PARTIAL"})
    assert B.routing(partial, _scored(CUR_OK), CLOSED)["decision"] == "LOOP_CLOSED"


def test_a_failed_cal_decides_alone_and_current_waits_for_a_passed_one():
    """Codex r3: current runs only when cal has no UNSAFE, tool failure or blind verifier."""
    r = B.routing(_scored({**CAL_OK, "codeql/go/def_use": "UNSAFE"}), None, None)
    assert r["decision"] == "UNSAFE" and r["current_run"] is False
    assert B.routing(_scored({**CAL_OK, "codeql/python/def_use": "BLIND"}), None, None)["decision"] \
        == "CALIBRATION_BLIND"
    with pytest.raises(ValueError):
        B.routing(_scored(CAL_OK), None, None)


def test_cal_gate(tmp_path):
    rel = "experiments/hop_bridge/relations.yaml"
    files = {rel: B._sha256(ROOT / rel)}

    def gate(classes, files=files):
        f = tmp_path / "cal.json"
        f.write_text(json.dumps({"provenance": {"files": files}, **_scored(classes)}))
        return B.cal_gate(f)

    assert B.cal_gate(tmp_path / "missing.json") == ["no cal result"]
    assert gate(CAL_OK) == []
    assert gate(CAL_OK, {rel: "0" * 64}) == [f"{rel} changed since cal"]
    assert gate({**CAL_OK, "codeql/go/range_element": "BLIND"}) == \
        ["cal calibration_blind: ['codeql/go/range_element']"]
    assert gate({**CAL_OK, "codeql/go/def_use": "INCONCLUSIVE_TOOL_FAILURE"}) == \
        ["cal tool_failure: ['codeql/go/def_use']"]
