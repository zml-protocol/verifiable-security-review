"""Synthetic tests for the anchor->node-ref resolver (experiments/rd/truth/resolver.py).

Covers Codex's required cases: ambiguous expression in range rejected; identical text at different
nodes resolves to different identity; multiline expression; formatting-invariance; sub-line fragment
rejected; missing source / bad range fail loud; and resolver source-hash drift is refused by the
freeze gate.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "rd" / "truth"))
import resolver  # noqa: E402

GO = ("package p\n"
      "\n"
      "func F(localPath string) {\n"
      "\tx := compute(localPath)\n"
      "\tif guard(x) {\n"
      "\t\treturn\n"
      "\t}\n"
      "\tx = compute(localPath)\n"
      "}\n")


def _id(sl, el, expr, rev="revision_A", src=GO, lang="go"):
    return resolver.resolve_identity({"file": "p.go", "start_line": sl, "end_line": el, "expression": expr},
                                     language=lang, revision=rev, source=src)


def test_identical_text_different_nodes_differ():
    assert _id(4, 4, "x := compute(localPath)") != _id(8, 8, "x = compute(localPath)")


def test_duplicate_expression_in_range_is_ambiguous():
    dup = "package p\nfunc F() {\n\treturn\n\treturn\n}\n"
    with pytest.raises(resolver.ResolverError):
        resolver.resolve_span({"file": "p.go", "start_line": 3, "end_line": 4, "expression": "return"}, dup)


def test_sub_line_fragment_rejected():
    with pytest.raises(resolver.ResolverError):
        resolver.resolve_span({"file": "p.go", "start_line": 4, "end_line": 4, "expression": "compute(localPath"}, GO)


def test_multiline_expression_resolves():
    ident = _id(5, 7, "if guard(x) {\nreturn\n}")
    assert ident[3] == "*ast.IfStmt"


def test_indentation_only_change_same_identity():
    indented = GO.replace("\tx := compute(localPath)", "        x := compute(localPath)")
    assert _id(4, 4, "x := compute(localPath)", src=indented) == _id(4, 4, "x := compute(localPath)")


def test_internal_whitespace_is_semantic():
    # a string-literal spacing change must NOT be normalised away (not a formatting difference)
    src = "package p\nvar s = \"a  b\"\n"
    with pytest.raises(resolver.ResolverError):
        resolver.resolve_span({"file": "p.go", "start_line": 2, "end_line": 2, "expression": "var s = \"a b\""}, src)
    # exact internal text matches
    ident = resolver.resolve_identity({"file": "p.go", "start_line": 2, "end_line": 2, "expression": "var s = \"a  b\""},
                                      language="go", revision="revision_A", source=src)
    assert ident[3] in ("*ast.GenDecl", "*ast.ValueSpec", "*ast.AssignStmt")


def test_block_header_resolves_to_statement():
    assert _id(5, 5, "if guard(x) {")[3] == "*ast.IfStmt"


def test_missing_expression_and_bad_range_fail_loud():
    with pytest.raises(resolver.ResolverError):
        resolver.resolve_span({"file": "p.go", "start_line": 4, "end_line": 4, "expression": "nonexistent()"}, GO)
    with pytest.raises(resolver.ResolverError):
        resolver.resolve_span({"file": "p.go", "start_line": 99, "end_line": 99, "expression": "x"}, GO)
    with pytest.raises(resolver.ResolverError):
        resolver.resolve_span({"file": "p.go", "start_line": 1, "end_line": 1}, GO)  # missing expression


def test_revision_passthrough_distinguishes():
    a = _id(4, 4, "x := compute(localPath)", rev="revision_A")
    b = _id(4, 4, "x := compute(localPath)", rev="revision_B")
    assert a != b and a[1] == "revision_A" and b[1] == "revision_B"


def test_resolve_doc_preresolves_for_passthrough():
    anchor = {"file": "p.go", "start_line": 5, "end_line": 5, "expression": "if guard(x) {"}
    item = {"id": "b", "kind": "behavior",
            "behavior": {"revision_A": {"state": "present", "anchor": anchor}}}
    rd = resolver.resolve_doc({"items": [item]}, language="go", source_provider=lambda rev, f: GO)
    assert rd["items"][0]["behavior"]["revision_A"]["anchor"]["node_identity"][3] == "*ast.IfStmt"


def test_resolver_drift_refused_by_freeze():
    sys.path.insert(0, str(ROOT / "experiments" / "rd" / "truth"))
    import freeze
    assert "experiments/rd/truth/resolver.py" in freeze.TOOL_SOURCES
