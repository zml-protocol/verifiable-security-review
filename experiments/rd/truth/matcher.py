"""The single frozen production anchor matcher: canonical syntax-node identity (PREREGISTRATION §15.1 item 5).

This is the one implementation the truth tooling and the scorer may use. It is NOT a narrow
`(revision, path, sha256)` tuple and it does NOT use line overlap as identity. Identity is a
position-independent syntax-node identity, so:

- two syntactically identical nodes at different positions in one file are **distinct** (their
  structural path differs);
- the same node under different equivalent representations (reformatting/whitespace) is the **same**
  (structural path and the position-stripped content digest are formatting-invariant);
- a different revision is a different identity (the revision is part of the tuple); there is no
  cross-revision "same object" connector here — one would have to be added to the protocol explicitly.

Identity tuple: ``(language, revision, path, node_type, structural_path, content_digest)`` where
``structural_path`` is the root→node child-ordinal path (children in source order).

Parsers (recorded in the provenance manifest, not swappable at runtime):
- python: CPython stdlib ``ast``;
- go: ``go/parser`` via the pinned helper ``goresolver/node_id.go`` (parse mode 0, no comments),
  run with the bundled Go toolchain.

Production binds to THIS module's ``node_identity`` only. Callers may not pass an arbitrary
``module:function``; a provenance/hash mismatch fails loud.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
TRUTH_DIR = HERE.parent
REPO = HERE.parents[3]
GORESOLVER = TRUTH_DIR / "goresolver"
MANIFEST = TRUTH_DIR / "matcher-provenance.json"

FROZEN_FUNCTION = "node_identity"
# The only accepted --anchor-matcher spec (module basename : function). Anything else is refused.
FROZEN_SPEC = f"matcher:{FROZEN_FUNCTION}"

IDENTITY_TUPLE = ("language", "revision", "path", "node_type", "structural_path", "content_digest")


class MatcherError(RuntimeError):
    """Fail-loud: provenance mismatch, an unparseable input, or an unresolvable span."""


# ---- provenance --------------------------------------------------------------------------------

def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _go_binary() -> str:
    cands = sorted(REPO.glob(".cache/toolchains/go*/bin/go"))
    if cands:
        return str(cands[-1])
    return "go"


def _go_version() -> str:
    try:
        out = subprocess.run([_go_binary(), "version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        raise MatcherError(f"go toolchain unavailable: {e}")
    if out.returncode != 0:
        raise MatcherError(f"go version failed: {out.stderr.strip()}")
    # "go version go1.26.8 linux/amd64" -> "go1.26.8"
    parts = out.stdout.split()
    return parts[2] if len(parts) >= 3 else out.stdout.strip()


def build_provenance() -> dict:
    """Compute the provenance manifest from the current files (used to (re)write MANIFEST)."""
    return {
        "matcher": {
            "file": str(HERE.relative_to(REPO)),
            "function": FROZEN_FUNCTION,
            "spec": FROZEN_SPEC,
            "sha256": _sha256_file(HERE),
        },
        "identity_tuple": list(IDENTITY_TUPLE),
        "resolvers": {
            "python": {"parser": "cpython-stdlib-ast",
                       "python_version": f"{sys.version_info.major}.{sys.version_info.minor}"},
            "go": {"parser": "go/parser(mode=0)",
                   "go_version": _go_version(),
                   "helper": str((GORESOLVER / "node_id.go").relative_to(REPO)),
                   "helper_sha256": _sha256_file(GORESOLVER / "node_id.go"),
                   "go_mod_sha256": _sha256_file(GORESOLVER / "go.mod")},
        },
    }


def write_provenance() -> dict:
    doc = build_provenance()
    MANIFEST.write_text(json.dumps(doc, indent=2) + "\n")
    return doc


def check_provenance() -> dict:
    """Fail loud unless every pinned file still hashes to the frozen manifest value."""
    if not MANIFEST.exists():
        raise MatcherError(f"missing matcher provenance manifest: {MANIFEST}")
    m = json.loads(MANIFEST.read_text())
    if _sha256_file(HERE) != m["matcher"]["sha256"]:
        raise MatcherError("matcher.py has changed since it was frozen (sha256 mismatch); refusing")
    if _sha256_file(GORESOLVER / "node_id.go") != m["resolvers"]["go"]["helper_sha256"]:
        raise MatcherError("go resolver helper has changed since it was frozen (sha256 mismatch); refusing")
    if _sha256_file(GORESOLVER / "go.mod") != m["resolvers"]["go"]["go_mod_sha256"]:
        raise MatcherError("go resolver go.mod has changed since it was frozen (sha256 mismatch); refusing")
    return m


def load_frozen_matcher(spec: str | None = None):
    """Return the one frozen matcher callable after a provenance check. A non-None spec must equal
    the frozen spec exactly — callers cannot point the tooling at a different callable."""
    if spec is not None and spec != FROZEN_SPEC:
        raise MatcherError(
            f"refusing matcher {spec!r}: production is bound to the single frozen matcher {FROZEN_SPEC!r}"
        )
    check_provenance()
    return node_identity


# ---- resolvers ---------------------------------------------------------------------------------

def _target(ref: dict) -> tuple[tuple[int, int], tuple[int, int]]:
    t = ref.get("target") or {}
    try:
        start = (int(t["start_line"]), int(t["start_col"]))
        end = (int(t["end_line"]), int(t["end_col"]))
    except (KeyError, TypeError, ValueError) as e:
        raise MatcherError(f"anchor needs target start/end line+col: {e}")
    return start, end


def _py_pos(node) -> tuple[tuple[int, int], tuple[int, int]] | None:
    if not hasattr(node, "lineno") or node.lineno is None:
        return None
    end_line = getattr(node, "end_lineno", None)
    end_col = getattr(node, "end_col_offset", None)
    if end_line is None or end_col is None:
        return None
    return (node.lineno, node.col_offset), (end_line, end_col)


def _py_children_sorted(node) -> list:
    kids = list(ast.iter_child_nodes(node))
    # Stable sort by source position; position-less nodes keep field order at the front.
    return sorted(kids, key=lambda k: _py_pos(k)[0] if _py_pos(k) else (-1, -1))


def _python_identity(ref: dict) -> dict:
    source = ref.get("source")
    if not isinstance(source, str):
        raise MatcherError("python anchor needs full source text under 'source'")
    start, end = _target(ref)
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise MatcherError(f"python parse failed: {e}")

    def contains(node) -> bool:
        p = _py_pos(node)
        return p is not None and p[0] <= start and end <= p[1]

    node, path = tree, []
    while True:
        descended = False
        for i, kid in enumerate(_py_children_sorted(node)):
            if contains(kid):
                node, path = kid, path + [i]
                descended = True
                break
        if not descended:
            break
    if node is tree:
        raise MatcherError("no enclosing python node for the target span")
    return {
        "node_type": type(node).__name__,
        "structural_path": path,
        "content_digest": hashlib.sha256(
            ast.dump(node, annotate_fields=True, include_attributes=False).encode()
        ).hexdigest(),
    }


_GO_VERSION_CHECKED: list[str] = []


def _go_identity(ref: dict) -> dict:
    source = ref.get("source")
    if not isinstance(source, str):
        raise MatcherError("go anchor needs full source text under 'source'")
    (sl, sc), (el, ec) = _target(ref)
    if not _GO_VERSION_CHECKED:
        m = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
        want = (m.get("resolvers", {}).get("go", {}) or {}).get("go_version")
        got = _go_version()
        if want and got != want:
            raise MatcherError(f"go toolchain is {got!r}, frozen manifest pins {want!r}; refusing")
        _GO_VERSION_CHECKED.append(got)
    env = {**os.environ,
           "GOCACHE": str(REPO / ".cache" / "go-build"),
           "GOPATH": str(REPO / ".cache" / "gopath"),
           "GOFLAGS": "-mod=mod"}
    try:
        proc = subprocess.run(
            [_go_binary(), "run", ".", str(sl), str(sc), str(el), str(ec)],
            input=source, capture_output=True, text=True, cwd=str(GORESOLVER), env=env, timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise MatcherError(f"go resolver failed to run: {e}")
    if proc.returncode != 0:
        raise MatcherError(f"go resolver error: {proc.stderr.strip()}")
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise MatcherError(f"go resolver bad output: {e}: {proc.stdout!r}")
    return {"node_type": out["node_type"], "structural_path": out["structural_path"],
            "content_digest": out["content_digest"]}


_RESOLVERS = {"python": _python_identity, "go": _go_identity}


def node_identity(ref: dict) -> tuple:
    """The frozen canonical identity of the syntax node an anchor cites.

    `ref` keys: language ('python'|'go'), revision, path, source (full file text), and
    target = {start_line, start_col, end_line, end_col} (line 1-based, col 0-based).
    """
    if ref is None:
        raise MatcherError("anchor is None; the matcher never fabricates an identity")
    lang = ref.get("language")
    resolver = _RESOLVERS.get(lang)
    if resolver is None:
        raise MatcherError(f"unsupported language {lang!r}; the frozen vocabulary is {sorted(_RESOLVERS)}")
    revision, path = ref.get("revision"), ref.get("path")
    if revision is None or path is None:
        raise MatcherError("anchor needs 'revision' and 'path'")
    r = resolver(ref)
    return (lang, revision, path, r["node_type"], tuple(r["structural_path"]), r["content_digest"])


# ---- self-test (diagnostic exact-tuple path lives only here) -----------------------------------

def _self_test() -> None:
    # Python: two identical statements at different positions -> distinct identities.
    py = "def f():\n    return None\n\ndef g():\n    return None\n"
    a = node_identity({"language": "python", "revision": "head", "path": "m.py", "source": py,
                       "target": {"start_line": 2, "start_col": 4, "end_line": 2, "end_col": 15}})
    b = node_identity({"language": "python", "revision": "head", "path": "m.py", "source": py,
                       "target": {"start_line": 5, "start_col": 4, "end_line": 5, "end_col": 15}})
    assert a != b, "identical-text different-position python nodes must differ"
    assert a[3] == b[3] == "Return" and a[4] != b[4], (a, b)

    # Same node, different equivalent representation (extra blank line + spaces) -> equal.
    py2 = "def f():\n\n    return  None\n\ndef g():\n    return None\n"
    a2 = node_identity({"language": "python", "revision": "head", "path": "m.py", "source": py2,
                        "target": {"start_line": 3, "start_col": 4, "end_line": 3, "end_col": 16}})
    assert a2 == a, f"same python node under reformatting must match: {a2} vs {a}"

    # Different revision -> different identity (no same-object connector).
    a_base = node_identity({"language": "python", "revision": "base", "path": "m.py", "source": py,
                            "target": {"start_line": 2, "start_col": 4, "end_line": 2, "end_col": 15}})
    assert a_base != a and a_base[1] == "base"

    # Go: two identical returns -> distinct; reformatting -> equal.
    go = "package p\n\nfunc F() {\n\treturn\n}\n\nfunc G() {\n\treturn\n}\n"
    ga = node_identity({"language": "go", "revision": "head", "path": "m.go", "source": go,
                        "target": {"start_line": 4, "start_col": 1, "end_line": 4, "end_col": 7}})
    gb = node_identity({"language": "go", "revision": "head", "path": "m.go", "source": go,
                        "target": {"start_line": 8, "start_col": 1, "end_line": 8, "end_col": 7}})
    assert ga != gb and ga[3] == gb[3] == "*ast.ReturnStmt", (ga, gb)
    go2 = "package p\nfunc F() { return }\nfunc G() { return }\n"
    ga2 = node_identity({"language": "go", "revision": "head", "path": "m.go", "source": go2,
                         "target": {"start_line": 2, "start_col": 11, "end_line": 2, "end_col": 17}})
    assert ga2[4] == ga[4], f"same go node under reformatting must match path: {ga2} vs {ga}"

    # Enforcement: a foreign matcher spec is refused; the frozen spec is accepted.
    try:
        load_frozen_matcher("evil:owned")
    except MatcherError:
        pass
    else:
        raise AssertionError("a foreign matcher spec was not refused")
    assert load_frozen_matcher() is node_identity
    assert load_frozen_matcher(FROZEN_SPEC) is node_identity
    print("matcher self-test ok:", {"python_identity_len": len(a), "go_node": ga[3]})


if __name__ == "__main__":
    if "--write-provenance" in sys.argv:
        print(json.dumps(write_provenance(), indent=2))
    elif "--self-test" in sys.argv:
        _self_test()
    else:
        print(__doc__)
