"""Tests for the frozen per-fixture revision mapping (experiments/rd/truth/revision_map.py)."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "rd" / "truth"))
import revision_map as rm  # noqa: E402

FIXTURES = ("GHSA-fq2j-j8hc-8vw8", "GHSA-hx8v-g79f-8w5f", "PYSEC-2026-1868", "GHSA-xmfj-7pp5-fxr6",
            "GO-2026-6237", "GHSA-rmrf-g9r3-73pm", "GHSA-5gfj-64gh-mgmw", "GHSA-937x-gpqr-72gg")


def test_mapping_is_deterministic():
    for fid in FIXTURES:
        assert rm.seed_revision_map(fid) == rm.seed_revision_map(fid)
        m = rm.seed_revision_map(fid)
        assert set(m) == {"revision_A", "revision_B"}
        assert {m["revision_A"], m["revision_B"]} == {"vuln", "fixed"}


def test_mapping_not_degenerate_across_fixtures():
    roles = {rm.seed_revision_map(fid)["revision_A"] for fid in FIXTURES}
    assert roles == {"vuln", "fixed"}


def test_map_doc_relabels_canonical_to_outward():
    item = {"id": "b", "kind": "behavior",
            "behavior": {"vuln": {"state": "absent", "context": {"file": "x", "start_line": 1, "end_line": 1, "expression": "a"}},
                         "fixed": {"state": "present", "anchor": {"file": "x", "start_line": 1, "end_line": 1, "expression": "b"}}}}
    mapped = rm.map_doc({"items": [item]}, "GHSA-fq2j-j8hc-8vw8")
    slot = mapped["items"][0]["behavior"]
    assert set(slot) == {"revision_A", "revision_B"}
    m = rm.seed_revision_map("GHSA-fq2j-j8hc-8vw8")
    fixed_key = "revision_A" if m["revision_A"] == "fixed" else "revision_B"
    assert slot[fixed_key]["state"] == "present"


def test_second_remap_refused():
    item = {"id": "e", "kind": "entry",
            "entry": {"vuln": {"state": "present", "anchor": {"file": "x", "start_line": 1, "end_line": 1, "expression": "a"}},
                      "fixed": {"state": "present", "anchor": {"file": "x", "start_line": 1, "end_line": 1, "expression": "a"}}}}
    mapped = rm.map_doc({"items": [item]}, "GO-2026-6237")
    with pytest.raises(rm.RevisionMapError):
        rm.map_doc(mapped, "GO-2026-6237")


def test_non_canonical_slot_keys_rejected():
    item = {"id": "e", "kind": "entry",
            "entry": {"vuln": {"state": "present"}, "bogus": {"state": "present"}}}
    with pytest.raises(rm.RevisionMapError):
        rm.map_doc({"items": [item]}, "GHSA-fq2j-j8hc-8vw8")


def test_source_provider_keeps_label_and_source_in_sync():
    import resolver
    fid = next(f for f in FIXTURES if rm.seed_revision_map(f)["revision_A"] == "fixed")
    canonical = {"fixed": "package p\nfunc F() {\n\tsafe := true\n}\n",
                 "vuln": "package p\nfunc F() {\n\tx := 1\n}\n"}
    provider = rm.make_source_provider(fid, lambda role, f: canonical[role])
    marker = {"file": "p.go", "start_line": 3, "end_line": 3, "expression": "safe := true"}
    # revision_A maps to fixed -> provider returns the fixed source -> marker resolves
    resolver.resolve_identity(marker, language="go", revision="revision_A",
                              source=provider("revision_A", "p.go"))
    # revision_B maps to vuln -> marker absent -> fail loud
    with pytest.raises(resolver.ResolverError):
        resolver.resolve_identity(marker, language="go", revision="revision_B",
                                  source=provider("revision_B", "p.go"))


def test_pool_or_seed_drift_refused(tmp_path, monkeypatch):
    import json
    good = json.loads(rm.FREEZE_MANIFEST.read_text())
    bad = json.loads(json.dumps(good))
    bad["selection"]["pool_sha256"] = "0" * 64
    p = tmp_path / "freeze.json"
    p.write_text(json.dumps(bad))
    monkeypatch.setattr(rm, "FREEZE_MANIFEST", p)
    with pytest.raises(rm.RevisionMapError):
        rm.seed_revision_map("GHSA-fq2j-j8hc-8vw8")
    bad2 = json.loads(json.dumps(good))
    bad2["selection"]["seed"] = good["selection"]["seed"] + 1
    p2 = tmp_path / "freeze2.json"
    p2.write_text(json.dumps(bad2))
    monkeypatch.setattr(rm, "FREEZE_MANIFEST", p2)
    with pytest.raises(rm.RevisionMapError):
        rm.seed_revision_map("GHSA-fq2j-j8hc-8vw8")
