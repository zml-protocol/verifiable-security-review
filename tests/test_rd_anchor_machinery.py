"""Tests for the fixture-independent distractor anchor machinery (anchor_machinery.py)."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "rd" / "truth"))
import anchor_machinery as am  # noqa: E402
import resolver  # noqa: E402

SRC_A = ("package p\n"
         "func F() {\n"
         "\ta := 1\n"
         "\tb := 2\n"
         "\tc := use(a, b)\n"
         "\treturn\n"
         "}\n")
SRC_B = SRC_A.replace("\tb := 2\n", "\tb := 2 + 0\n")  # line 4 changed in B
PROVIDER = {"revision_A": SRC_A, "revision_B": SRC_B}


def _prov(rev, f):
    return PROVIDER[rev]


def test_relocate_moves_to_nearby_common_node():
    relocate = am.make_relocator("go", _prov)
    anchor = {"file": "p.go", "start_line": 3, "end_line": 3, "expression": "a := 1"}
    moved = relocate(anchor)
    assert moved is not None and moved["start_line"] != 3
    # valid and unique in BOTH revisions, and it is not the changed line 4
    assert moved["start_line"] != 4
    resolver.resolve_identity(moved, language="go", revision="revision_A", source=SRC_A)
    resolver.resolve_identity(moved, language="go", revision="revision_B", source=SRC_B)


def test_relocate_none_when_no_valid_neighbor():
    relocate = am.make_relocator("go", lambda rev, f: "package p\n")
    assert relocate({"file": "p.go", "start_line": 1, "end_line": 1, "expression": "package p"}) is None


def test_context_present_roundtrip():
    anchor = {"file": "p.go", "start_line": 3, "end_line": 3, "expression": "a := 1"}
    ctx = am.context_for(anchor)
    assert ctx == anchor
    assert am.present_for(ctx) == anchor


def test_rebuild_relabels_kind_keeps_slots():
    item = {"id": "q", "kind": "guard", "expected": "must_hold",
            "subject": {"revision_A": {"state": "present", "anchor": {"file": "x", "start_line": 1, "end_line": 1, "expression": "a"}}}}
    out = am.rebuild(item, "config")
    assert out["kind"] == "config" and out["subject"] == item["subject"]
    assert item["kind"] == "guard"  # original untouched


def test_malformed_input_fails_loud():
    for bad in (None, 5, {"file": "x"}):
        with pytest.raises(am.AnchorMachineryError):
            am.context_for(bad)
    with pytest.raises(am.AnchorMachineryError):
        am.rebuild("not a dict", "guard")


def test_in_tool_sources():
    import freeze
    assert "experiments/rd/truth/anchor_machinery.py" in freeze.TOOL_SOURCES
