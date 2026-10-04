import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HC = ROOT / "experiments" / "hop_chain"
sys.path.insert(0, str(HC))

import chain
import connector as C
import replicate as RP
import replicate_score as RS

needs_repos = pytest.mark.skipif(
    not all((ROOT / p).exists() for p in (".cache/repos/caddy.git", ".cache/repos/authlib.git",
                                           ".cache/repos/filebrowser.git")),
    reason="fixture repositories not built")

F = "f.go"


def n(line, col=2):
    return ("node", F, line, col)


def edge(i, a, b, rel="object_composition"):
    return {"id": i, "relation": rel, "a": a, "b": b}


FN = ("inside", "g.py", 10, 20)


# ---- the classifier -----------------------------------------------------------------------


def test_classes_in_order():
    entry, term = n(1), n(9)
    full = [edge("e1", n(1), n(5)), edge("e2", n(5), n(9))]
    assert chain.classify(full, entry, term, False, None) == {"class": "FULL_CHAIN", "length": 2}
    assert chain.classify(full, entry, term, True, None)["class"] == "QUALIFIER_GAP"
    guarded = [*full, edge("g", n(3), n(5), "guard_property")]
    assert chain.classify(guarded, entry, term, True, None)["class"] == "FULL_CHAIN"
    suffix = [edge("e2", n(5), n(9))]
    got = chain.classify(suffix, entry, term, False, None)
    assert got["class"] == "ENTRY_GAP" and got["longest_suffix_edges"] == 1  # a suffix only
    prefix = [edge("e1", n(1), n(5))]
    got = chain.classify(prefix, entry, term, False, None)
    assert got["class"] == "INTERNAL_GAP" and got["entry_prefix"] is True
    assert chain.classify([], entry, term, False, None)["class"] == "NO_EVIDENCE"


def test_a_function_continues_into_nodes_inside_it_only():
    entry, term = ("node", "a.py", 3, 5), ("inside", "b.py", 30, 31)
    inside = ("node", "g.py", 12, 9)
    outside = ("node", "g.py", 25, 9)
    ok = [edge("c", entry, FN, "call_typed_attribute"), edge("d", inside, term, "registry_dispatch")]
    assert chain.classify(ok, entry, term, False, None)["class"] == "FULL_CHAIN"
    bad = [edge("c", entry, FN, "call_typed_attribute"), edge("d", outside, term, "registry_dispatch")]
    assert chain.classify(bad, entry, term, False, None)["class"] == "ENTRY_GAP"


def test_same_object_connects_only_when_the_connector_proves_it():
    entry, term = n(198), n(215)
    edges = [edge("a", n(185), n(198)), edge("c", n(178), term)]  # same object: 198 store, 178 def
    proves = lambda a, b: {a, b} == {n(198), n(178)}
    assert chain.classify(edges, entry, term, False, None)["class"] == "ENTRY_GAP"
    assert chain.classify(edges, entry, term, False, proves)["class"] == "FULL_CHAIN"
    never = lambda a, b: False
    assert chain.classify(edges, entry, term, False, never)["class"] == "ENTRY_GAP"


def test_qualifier_may_attach_through_the_same_object():
    entry, term = n(198), n(215)
    edges = [edge("c", n(178), term), edge("g", n(179, 3), n(198), "guard_property")]
    proves = lambda a, b: {a, b} == {n(198), n(178)}
    assert chain.classify(edges, entry, term, True, proves)["class"] == "FULL_CHAIN"
    assert chain.classify(edges, entry, term, True, lambda a, b: False)["class"] == "ENTRY_GAP"


def test_paths_are_simple_and_bounded():
    entry, term = n(1), n(99)
    cycle = [edge("a", n(1), n(2)), edge("b", n(2), n(1)), edge("c", n(2), n(3))]
    assert chain.classify(cycle, entry, term, False, None)["class"] == "INTERNAL_GAP"
    long = [edge(f"e{i}", n(i), n(i + 1)) for i in range(1, 15)]
    assert chain.classify(long, n(1), n(13), False, None)["length"] == 12
    assert chain.classify(long, n(1), n(14), False, None)["class"] == "ENTRY_GAP"  # 13 edges: too long


def test_wilson():
    assert RS.wilson(0, 0) is None
    lo, hi = RS.wilson(10, 10)
    assert hi == 1.0 and 0.69 < lo < 0.73
    lo, hi = RS.wilson(5, 10)
    assert 0.23 < lo < 0.24 and 0.76 < hi < 0.77


# ---- the connector ------------------------------------------------------------------------


def test_connector_answers_from_rows_and_never_claims_difference():
    rows = [[F, 178, 2, "definition", "o", 178, 2], [F, 198, 2, "field_store", "o", 178, 2],
            [F, 215, 2, "field_store", "r", 84, 2]]
    c = C.Connector(rows)
    assert c.same_object(n(178), n(198)) == C.SAME
    assert c.same_object(n(198), n(215)) == C.NOT_PROVEN
    assert c.same_object(n(300), n(198)) == C.NOT_PROVEN  # an unknown node is never "different"
    assert c.same_object(("inside", F, 1, 9), n(198)) == C.NOT_PROVEN
    assert {C.SAME, C.NOT_PROVEN} == {"SAME_OBJECT", "NOT_PROVEN_SAME"}


FIXTURE_WORDS = ["caddy", "authlib", "filebrowser", "goodResponseHandler", "rpHandler",
                 "HandleResponse", "nameInArchive", "Routes", "StatusCode", "jws", "archive"]


def test_the_connector_query_names_no_fixture_symbol():
    import re

    text = re.sub(r"secreview/[\w-]+", "", C.QUERY.read_text())
    assert not [w for w in FIXTURE_WORDS if re.search(rf"\b{w}\b", text, re.IGNORECASE)]


def test_calibration_pairs_cover_every_truth_kind():
    for name in ("dev", "cal"):
        spec = yaml.safe_load((HC / "connector" / f"{name}.yaml").read_text())
        kinds = {p["truth"] for p in spec["pairs"]}
        assert kinds == {"same", "different", "not_always", "unprovable"}, name
        assert len({p["id"] for p in spec["pairs"]}) == len(spec["pairs"])


# ---- frozen inputs ------------------------------------------------------------------------


@needs_repos
def test_anchors_are_rule_g_of_the_frozen_golden():
    import diagnose as D

    frozen = RS.anchors(pilot=False)
    for fixture, revs in frozen.items():
        m = D.S.Matcher(fixture, False)
        for rev, a in revs.items():
            g = D.golden_ends(m, rev)
            assert (a["entry"], a["terminal"], a["needs_qualifier"]) == (
                g["entry"], g["terminal"], g["qualified"]), (fixture, rev)


def test_order_is_seeded_and_complete(tmp_path):
    from argparse import Namespace

    out = tmp_path / "o.txt"
    RP.order(Namespace(out=out))
    assert out.read_text() == (HC / "order.txt").read_text()
    blocks = RP.P.read_order(out)
    assert len(blocks) == 30 and len(set(blocks)) == 30


def test_the_replication_session_is_the_p_hybrid_2_initial_phase(tmp_path):
    cfg = RP.P.session_config("caddy-forward-auth", False, 0, tmp_path, "initial", None)
    assert cfg.phase == "initial" and cfg.initial_snapshot is None
    assert RP.P.PROMPT == (ROOT / "experiments" / "hop_propose" / "prompt.md").read_text()


def test_entry_gap_reports_the_longest_verified_suffix():
    # entry --- missing ---> A -> B -> C -> terminal, and A -> terminal directly
    entry, term = n(1), n(99)
    A, B, Cn = n(10), n(20), n(30)
    edges = [edge("ab", A, B), edge("bc", B, Cn), edge("ct", Cn, term), edge("at", A, term)]
    got = chain.classify(edges, entry, term, False, None)
    assert got["class"] == "ENTRY_GAP" and got["longest_suffix_edges"] == 3


def test_cycles_cannot_lengthen_a_suffix():
    entry, term = n(1), n(99)
    A, B = n(10), n(20)
    edges = [edge("ab", A, B), edge("ba", B, A), edge("at", A, term)]
    # B -> A -> terminal is the longest node-simple suffix; A -> B -> A -> terminal revisits A
    assert chain.classify(edges, entry, term, False, None)["longest_suffix_edges"] == 2


def test_same_object_counts_as_a_revisit():
    entry, term = n(1), n(99)
    A, A2, B = n(10), n(11), n(20)  # A and A2 are proven to be the same object
    proves = lambda a, b: {a, b} == {A, A2}
    edges = [edge("ab", A, B), edge("ba2", B, A2), edge("a2t", A2, term)]
    assert chain.classify(edges, entry, term, False, proves)["longest_suffix_edges"] == 2
    assert chain.classify(edges, entry, term, False, None)["longest_suffix_edges"] == 3


def test_an_ambiguous_node_never_joins():
    rows = [[F, 198, 2, "field_store", "o", 178, 2], [F, 198, 2, "field_store", "o", 181, 2],
            [F, 178, 2, "definition", "o", 178, 2]]
    assert C.Connector(rows).same_object(n(198), n(178)) == C.NOT_PROVEN


# ---- the connector gate (§12.1): no evaluation without a safe held-out calibration ------


def _fake_connector(tmp_path, monkeypatch, unsafe, rows=("caddy-forward-auth.base",
                                                         "caddy-forward-auth.head",
                                                         "filebrowser-archive-backslash.base",
                                                         "filebrowser-archive-backslash.head")):
    import gzip
    import hashlib
    import json

    frozen = tmp_path / "frozen"
    frozen.mkdir()
    files = {}
    for name in rows:
        data = json.dumps({"rows": []}).encode()
        (frozen / f"{name}.same_object.json.gz").write_bytes(gzip.compress(data))
        files[f"{name}.same_object.json.gz"] = {"sha256_json": hashlib.sha256(data).hexdigest()}
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    (frozen / "manifest.json").write_text(json.dumps({"query_sha256": sha(C.QUERY), "files": files}))
    cal = tmp_path / "chain-connector-cal.json"
    cal.write_text(json.dumps({"set": "cal", "unsafe": unsafe, "query_sha256": sha(C.QUERY),
                               "pairs_sha256": sha(HC / "connector" / "cal.yaml")}))
    monkeypatch.setattr(C, "FROZEN", frozen)
    monkeypatch.setattr(C, "CAL_RESULT", cal)


def test_an_unsafe_calibration_blocks_the_run_even_with_eval_rows(tmp_path, monkeypatch):
    from argparse import Namespace

    _fake_connector(tmp_path, monkeypatch, unsafe=["cd3"])  # stale rows exist
    assert any(p.startswith("CONNECTOR_CALIBRATION_FAILED") for p in RP.formal_preconditions())
    args = Namespace(pilot=False, allow_dirty=True, order=HC / "order.txt")
    with pytest.raises(SystemExit, match="no evaluation session starts"):
        RP.run(args)
    assert RS.score(pilot=False)["status"] == "CONNECTOR_CALIBRATION_FAILED"


def test_a_missing_eval_row_is_a_protocol_failure_not_a_fallback(tmp_path, monkeypatch):
    _fake_connector(tmp_path, monkeypatch, unsafe=[],
                    rows=("caddy-forward-auth.base", "caddy-forward-auth.head",
                          "filebrowser-archive-backslash.base"))
    assert C.gate() == []
    r = RS.score(pilot=False)
    assert r["status"] == "PROTOCOL_INVALID"
    assert r["problems"] == ["missing connector rows filebrowser-archive-backslash.head.same_object.json.gz"]
    assert "blocks" not in r  # no chain classes at all, under any connector


def test_a_changed_query_or_pair_file_voids_the_calibration(tmp_path, monkeypatch):
    import json

    _fake_connector(tmp_path, monkeypatch, unsafe=[])
    cal = json.loads(C.CAL_RESULT.read_text())
    C.CAL_RESULT.write_text(json.dumps({**cal, "query_sha256": "0" * 64}))
    assert C.gate() == ["SameObject.ql changed after the calibration"]


def test_the_held_out_calibration_runs_once(tmp_path, monkeypatch):
    from argparse import Namespace

    _fake_connector(tmp_path, monkeypatch, unsafe=[])
    with pytest.raises(SystemExit, match="runs once"):
        C.calibrate(Namespace(set="cal"))
