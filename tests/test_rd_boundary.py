import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RD = ROOT / "experiments" / "rd"
sys.path.insert(0, str(RD / "boundary"))

import check as C

needs_repos = pytest.mark.skipif(
    not all((ROOT / ".cache/fixtures" / r).exists() for r in ("rdbound-go", "rdbound-py", "rdscen-go", "rdscen-py")),
    reason="RD boundary modules not built (fixtures/_rdbound/build.py)")


def _gen():
    spec = importlib.util.spec_from_file_location("rd_gen_cases", RD / "boundary" / "gen_cases.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@needs_repos
def test_boundary_cases_are_clean():
    assert C.problems() == []


@needs_repos
def test_case_files_are_exactly_what_the_generator_writes():
    g = _gen()
    rel, rel_labels = g.relation_cases()
    req, req_labels = g.requirement_cases()
    g.opaque(rel, rel_labels, req, req_labels)
    assert rel == C.load("relation_cases.yaml")
    assert req == C.load("requirement_cases.yaml")
    assert rel_labels == C.load("relation_labels.yaml")["labels"]
    assert req_labels == C.load("requirement_labels.yaml")["labels"]


RETIRED = ["authlib", "caddy", "filebrowser", "copyHeaderRoutes", "goodResponseHandler", "NameInArchive",
           "nameInArchive", "deserialize_compact", "jws_algs", "forwardauth"]


def test_definitions_and_modules_name_no_fixture():
    for path in (RD / "definitions.yaml", ROOT / "fixtures/_rdbound/build.py"):
        text = path.read_text().lower()
        assert not [w for w in RETIRED if w.lower() in text], path.name


def test_every_rule_id_is_unique_and_every_relation_is_defined():
    ids = C.rule_ids()
    assert len(ids) == len(set(ids))
    defs = yaml.safe_load((RD / "definitions.yaml").read_text())["relations"]
    sys.path.insert(0, str(ROOT / "experiments" / "hop_bridge"))
    import bridge
    vocab = set(bridge.relations("go")) | set(bridge.relations("python"))
    assert set(defs) == vocab


def test_leak_check_catches_labels_and_names():
    assert C.leaks({"set": "x", "hops": [{"id": "r01", "label": True}]}) == ["x.hops[0].label"]
    assert C.leaks({"set": "x", "items": [{"id": "q01", "name": "s1-entry"}]}) == ["x.items[0].name"]


def test_osv_snapshot_copy_matches_the_manifest_when_present():
    import json
    sys.path.insert(0, str(RD))
    import osv_verify
    local = ROOT / json.loads((RD / "osv-snapshot.json").read_text())["local_dir"]
    if not local.exists():
        pytest.skip("no local snapshot copy")
    assert osv_verify.problems(local) == []


# ---- decidability comparison (decide.py), on synthetic inputs ---------------------------------

sys.path.insert(0, str(RD / "boundary"))
import decide as D


def _author():
    return {"r01": {"label": "TRUE", "rule": "OC-3", "tier": "boundary"},
            "r02": {"label": "FALSE", "rule": "OC-1", "tier": "core"},
            "q01": {"label": "REQUIRED", "rule": "EN-2", "tier": "core"},
            "q02": {"label": "NOT_REQUIRED", "rule": "QU-3", "tier": "boundary"}}


GROUPS = {"r01": "go/object_composition", "r02": "go/object_composition", "q01": "entry", "q02": "guard"}


def test_full_agreement_is_admissible():
    labels = {cid: v["label"] for cid, v in _author().items()}
    out = D.compare(_author(), {"a": labels, "b": dict(labels)}, GROUPS)
    assert all(g["status"] == "AGREED" and g["outcome_without_revision"] == "ADMISSIBLE" for g in out.values())


def test_boundary_dispute_makes_an_indeterminate_region_and_core_dispute_exits_or_escalates():
    labels = {cid: v["label"] for cid, v in _author().items()}
    a = dict(labels)
    b = {**labels, "r01": "FALSE", "q02": "INDETERMINATE"}
    out = D.compare(_author(), {"a": a, "b": b}, GROUPS)
    assert out["go/object_composition"]["outcome_without_revision"] == "INDETERMINATE_BOUNDARY"
    assert out["go/object_composition"]["indeterminate_rules"] == ["OC-3"]
    assert out["guard"]["outcome_without_revision"] == "INDETERMINATE_BOUNDARY"  # an INDETERMINATE never agrees
    b = {**labels, "r02": "TRUE", "q01": "NOT_REQUIRED"}
    out = D.compare(_author(), {"a": a, "b": b}, GROUPS)
    assert out["go/object_composition"]["outcome_without_revision"] == "EXIT_VOCABULARY"
    assert out["entry"]["outcome_without_revision"] == "ESCALATE"  # entry cannot leave the vocabulary


def test_judge_files_accept_unquoted_yaml_and_require_the_attestation(tmp_path):
    manifest = {"relations": ["r01"], "requirements": ["q01"]}
    f = tmp_path / "j.yaml"
    f.write_text("reviewer: {type: model, name: \"X, new conversation\", date: 2026-10-02, attestation: "
                 "{independent: true, saw_author_labels: false, saw_project_history: false}}\n"
                 "relations:\n  r01: {label: TRUE}\nrequirements:\n  q01: {label: REQUIRED}\n")
    doc, problems = D.load_judge(f, manifest)
    assert problems == [] and doc["relations"]["r01"] == "TRUE" and doc["reviewer"]["date"] == "2026-10-02"
    f.write_text(f.read_text().replace("saw_author_labels: false", "saw_author_labels: true"))
    assert D.load_judge(f, manifest)[0] is None
    f.write_text("reviewer: {type: model, name: X, attestation: {independent: true, saw_author_labels: false, "
                 "saw_project_history: false}}\nrelations: {}\nrequirements:\n  q01: {label: REQUIRED}\n")
    assert any("ids differ" in p for p in D.load_judge(f, manifest)[1])


@needs_repos
def test_sheet_shows_no_label_rule_tier_or_name():
    sys.path.insert(0, str(RD / "boundary"))
    import sheet as S
    rel, req = C.load("relation_cases.yaml"), C.load("requirement_cases.yaml")
    text = S.sheet(rel, req)
    # a reason may paraphrase a rule, and the definitions are shown verbatim: check outside them
    start, end = text.index("## Definitions (verbatim)"), text.index("## Part 1. Relation cases")
    cases = text[:start] + text[end:]
    labels = C.load("relation_labels.yaml")["labels"] | C.load("requirement_labels.yaml")["labels"]
    for v in labels.values():
        assert v["name"] not in text and v["reason"] not in cases
    assert "tier" not in text and "core" not in text.lower().replace("score", "")
    for word in ("PREREGISTRATION", "Codex", "hop_verify", "hop_bridge", "Frozen"):
        assert word not in text, word


@needs_repos
def test_a_revision_round_relabels_exactly_the_revised_groups():
    import sheet as S
    rel, req = C.load("relation_cases.yaml"), C.load("requirement_cases.yaml")
    qualifiers = {"guard", "transform", "config", "dispatch_target"}  # QU-1 governs all four
    r2, q2 = S.subset(rel, req, qualifiers)
    assert r2["hops"] == []
    assert {it.get("kind") for it in q2["items"]} == qualifiers
    full = [it["id"] for it in req["items"] if it.get("kind") in qualifiers]
    assert [it["id"] for it in q2["items"]] == full  # all of the revised groups' items
    text = S.sheet(r2, q2)
    assert "Part 1" not in text and "relation cases" not in text
    assert all(sc["domain"] in text for sc in q2["scenarios"].values())
    assert "relations: {}" in S.template(r2, q2)
