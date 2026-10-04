"""Invariants for the frozen production anchor matcher (experiments/rd/truth/matcher.py).

Covers Codex's C.1 test list: identical-text/different-position nodes differ; the same node under an
equivalent representation matches; a different revision differs; a changed matcher file is refused;
and a foreign matcher spec is refused. Go cases are skipped if the bundled toolchain is unavailable.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "rd" / "truth"))
import matcher  # noqa: E402


def _go_ok() -> bool:
    try:
        return subprocess.run([matcher._go_binary(), "version"], capture_output=True).returncode == 0
    except OSError:
        return False


go_required = pytest.mark.skipif(not _go_ok(), reason="bundled Go toolchain unavailable")

PY = "def f():\n    return None\n\ndef g():\n    return None\n"


def _py(src, sl, sc, el, ec, rev="head"):
    return matcher.node_identity({"language": "python", "revision": rev, "path": "m.py",
                                  "source": src, "target": {"start_line": sl, "start_col": sc,
                                                             "end_line": el, "end_col": ec}})


def test_python_identical_text_different_position_differ():
    a = _py(PY, 2, 4, 2, 15)
    b = _py(PY, 5, 4, 5, 15)
    assert a != b and a[3] == b[3] == "Return" and a[4] != b[4]


def test_python_same_node_reformatted_matches():
    a = _py(PY, 2, 4, 2, 15)
    reformatted = "def f():\n\n    return  None\n\ndef g():\n    return None\n"
    a2 = _py(reformatted, 3, 4, 3, 16)
    assert a2 == a


def test_python_different_revision_differs():
    assert _py(PY, 2, 4, 2, 15, rev="base") != _py(PY, 2, 4, 2, 15, rev="head")


@go_required
def test_go_identical_text_different_position_differ():
    go = "package p\n\nfunc F() {\n\treturn\n}\n\nfunc G() {\n\treturn\n}\n"
    a = matcher.node_identity({"language": "go", "revision": "head", "path": "m.go", "source": go,
                               "target": {"start_line": 4, "start_col": 1, "end_line": 4, "end_col": 7}})
    b = matcher.node_identity({"language": "go", "revision": "head", "path": "m.go", "source": go,
                               "target": {"start_line": 8, "start_col": 1, "end_line": 8, "end_col": 7}})
    assert a != b and a[3] == b[3] == "*ast.ReturnStmt" and a[4] != b[4]


@go_required
def test_go_same_node_reformatted_matches():
    go = "package p\n\nfunc F() {\n\treturn\n}\n"
    go2 = "package p\nfunc F() { return }\n"
    a = matcher.node_identity({"language": "go", "revision": "head", "path": "m.go", "source": go,
                               "target": {"start_line": 4, "start_col": 1, "end_line": 4, "end_col": 7}})
    a2 = matcher.node_identity({"language": "go", "revision": "head", "path": "m.go", "source": go2,
                                "target": {"start_line": 2, "start_col": 11, "end_line": 2, "end_col": 17}})
    assert a2[4] == a[4] and a2[3] == a[3]


def test_foreign_matcher_spec_refused():
    with pytest.raises(matcher.MatcherError):
        matcher.load_frozen_matcher("evil:owned")
    assert matcher.load_frozen_matcher() is matcher.node_identity
    assert matcher.load_frozen_matcher(matcher.FROZEN_SPEC) is matcher.node_identity


def test_changed_matcher_file_refused(tmp_path, monkeypatch):
    bad = json.loads(matcher.MANIFEST.read_text())
    bad["matcher"]["sha256"] = "0" * 64  # pretend the frozen hash no longer matches the live file
    p = tmp_path / "bad-manifest.json"
    p.write_text(json.dumps(bad))
    monkeypatch.setattr(matcher, "MANIFEST", p)
    with pytest.raises(matcher.MatcherError):
        matcher.check_provenance()
    with pytest.raises(matcher.MatcherError):
        matcher.load_frozen_matcher()


def test_changed_go_helper_refused(tmp_path, monkeypatch):
    bad = json.loads(matcher.MANIFEST.read_text())
    bad["resolvers"]["go"]["helper_sha256"] = "0" * 64
    p = tmp_path / "bad-manifest.json"
    p.write_text(json.dumps(bad))
    monkeypatch.setattr(matcher, "MANIFEST", p)
    with pytest.raises(matcher.MatcherError):
        matcher.check_provenance()


def test_none_anchor_fails_loud():
    with pytest.raises(matcher.MatcherError):
        matcher.node_identity(None)
