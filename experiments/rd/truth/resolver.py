"""Anchor -> node-ref resolver: the wiring between the frozen anchor schema and the frozen matcher.

Harness wiring bug fix (PREREGISTRATION §15): C.1 froze the matcher (node-ref + column span input)
and the truth tooling froze the anchor schema `{file, start_line, end_line, expression}` separately,
but nothing connected the two — `agreement.py` loads the matcher yet the anchors reaching it cannot
be consumed. This module is that connector. It is strict, conservative and generic:

1. read the file's source at the given revision (caller supplies it);
2. locate `expression` ONLY within `[start_line, end_line]`, comparing whitespace-normalised full
   lines; the match must be UNIQUE — 0 or >1 candidates fail loud;
3. the matched block must be whole lines (a sub-line fragment matches nothing and is rejected — the
   resolver never silently grows or shrinks the span);
4. build the matcher node-ref over that span;
5. the frozen `matcher.node_identity()` alone decides identity — the resolver defines no equivalence.

To keep every frozen tool unchanged, the production flow PRE-RESOLVES each anchor/context in a truth
or judge doc to its frozen identity (`resolve_doc`), then runs the unchanged `agreement.check` with an
identity passthrough. No `agreement.py`/`matcher.py` source is modified.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import matcher

HERE = Path(__file__).resolve()
SLOT_KEYS = ("revision_A", "revision_B")  # agreement.py's frozen slot keys (post seed-mapping)


class ResolverError(RuntimeError):
    """Fail loud: ambiguous/absent expression, a fragment, or missing source."""


def _norm(line: str) -> str:
    # Tolerate only leading/trailing indentation. Internal whitespace is program semantics (string
    # literals, token spacing) and must match exactly — the resolver is a locator, not a formatter;
    # the frozen matcher alone owns formatting-invariant *identity*.
    return line.strip()


def resolve_span(anchor: dict, source: str) -> tuple[int, int, int, int]:
    """Return the (start_line, start_col, end_line, end_col) span of `expression` inside the anchor's
    line range. Lines 1-based, cols 0-based; whole-line, whitespace-normalised, UNIQUE match only."""
    for key in ("file", "start_line", "end_line", "expression"):
        if key not in anchor:
            raise ResolverError(f"anchor missing {key!r}: {anchor}")
    try:
        sl, el = int(anchor["start_line"]), int(anchor["end_line"])
    except (TypeError, ValueError) as e:
        raise ResolverError(f"anchor line numbers not integers: {e}")
    if sl < 1 or el < sl:
        raise ResolverError(f"bad anchor line range [{sl},{el}]")
    lines = source.split("\n")
    if el > len(lines):
        raise ResolverError(f"anchor range [{sl},{el}] exceeds file length {len(lines)}")
    expr_lines = [ln for ln in anchor["expression"].split("\n")]
    expr_norm = [_norm(ln) for ln in expr_lines]
    while expr_norm and expr_norm[0] == "":
        expr_norm.pop(0); expr_lines.pop(0)
    while expr_norm and expr_norm[-1] == "":
        expr_norm.pop(); expr_lines.pop()
    if not expr_norm:
        raise ResolverError("anchor expression is empty")
    k = len(expr_norm)
    win = range(sl - 1, el - 1 - k + 2)  # 0-based start indices whose k-line block fits in [sl,el]
    matches = [i for i in win if all(_norm(lines[i + j]) == expr_norm[j] for j in range(k))]
    if len(matches) == 0:
        raise ResolverError(
            f"expression not found as whole normalised line(s) in {anchor['file']} "
            f"[{sl},{el}]: {anchor['expression']!r}"
        )
    if len(matches) > 1:
        raise ResolverError(
            f"expression is ambiguous ({len(matches)} matches) in {anchor['file']} [{sl},{el}]: "
            f"{anchor['expression']!r}; tighten the line range"
        )
    m = matches[0]
    start_line = m + 1
    start_col = len(lines[m]) - len(lines[m].lstrip())
    end_line = m + k
    end_col = len(lines[m + k - 1].rstrip())
    return start_line, start_col, end_line, end_col


def resolve_identity(anchor: dict, *, language: str, revision: str, source: str) -> tuple:
    """Resolve one anchor/context to the frozen node identity. `revision` is a passthrough label
    carried into the identity tuple; `source` is the file's text at that revision."""
    sl, sc, el, ec = resolve_span(anchor, source)
    ref = {"language": language, "revision": revision, "path": anchor["file"], "source": source,
           "target": {"start_line": sl, "start_col": sc, "end_line": el, "end_col": ec}}
    try:
        return matcher.node_identity(ref)
    except matcher.MatcherError as e:
        raise ResolverError(f"matcher rejected the resolved node-ref: {e}")


def resolve_doc(doc: dict, *, language: str, source_provider) -> dict:
    """Return a copy of a truth/judge doc with every slot anchor/context replaced by its frozen node
    identity, so the unchanged `agreement.check` can run with an identity passthrough.

    `source_provider(revision, file) -> str` returns the file text at that revision (fail loud if it
    cannot). Slots are dicts keyed by SLOT_KEYS; each revision holds {state, anchor|context}.
    """
    out = copy.deepcopy(doc)

    def walk(container: dict) -> None:
        for value in container.values():
            if isinstance(value, dict) and set(value) & set(SLOT_KEYS):
                for rev, realization in value.items():
                    if rev not in SLOT_KEYS or not isinstance(realization, dict):
                        continue
                    key = "anchor" if realization.get("state") == "present" else (
                        "context" if realization.get("state") == "absent" else None)
                    if key is None or realization.get(key) is None:
                        continue
                    src = source_provider(rev, realization[key]["file"])
                    realization[key] = {"node_identity": list(
                        resolve_identity(realization[key], language=language, revision=rev, source=src))}

    for item in out.get("items", []) or []:
        if isinstance(item, dict):
            walk(item)
    for m in out.get("missing", []) or []:
        if isinstance(m, dict):
            walk(m)
    return out


def source_hash() -> str:
    return hashlib.sha256(HERE.read_bytes()).hexdigest()


def _self_test() -> None:
    go = ("package p\n"                      # 1
          "\n"                                # 2
          "func F(localPath string) {\n"      # 3
          "\tx := compute(localPath)\n"       # 4
          "\tif guard(x) {\n"                 # 5
          "\t\treturn\n"                       # 6
          "\t}\n"                             # 7
          "\tx = compute(localPath)\n"        # 8  (same text as line 4, different node)
          "}\n")                              # 9
    # whole-line unique match within a tight range -> resolves; the two identical lines differ.
    a4 = resolve_identity({"file": "p.go", "start_line": 4, "end_line": 4, "expression": "x := compute(localPath)"},
                          language="go", revision="revision_A", source=go)
    a8 = resolve_identity({"file": "p.go", "start_line": 8, "end_line": 8, "expression": "x = compute(localPath)"},
                          language="go", revision="revision_A", source=go)
    assert a4 != a8, "identical-looking lines at different nodes must differ"
    # ambiguous range (same expr twice) -> reject
    try:
        resolve_span({"file": "p.go", "start_line": 4, "end_line": 8, "expression": "x := compute(localPath)"}, go)
    except ResolverError:
        pass
    else:
        # line 4 only has `:=`; broaden expression to one present twice
        pass
    dup = "package p\nfunc F() {\n\treturn\n\treturn\n}\n"
    try:
        resolve_span({"file": "p.go", "start_line": 3, "end_line": 4, "expression": "return"}, dup)
        raise AssertionError("duplicate expression in range was not rejected")
    except ResolverError:
        pass
    # sub-line fragment -> reject (not a whole normalised line)
    try:
        resolve_span({"file": "p.go", "start_line": 4, "end_line": 4, "expression": "compute(localPath"}, go)
        raise AssertionError("sub-line fragment was not rejected")
    except ResolverError:
        pass
    # indentation-only change still locates (resolver tolerates leading/trailing whitespace only)
    go_indent = go.replace("\tx := compute(localPath)", "        x := compute(localPath)")
    a4b = resolve_identity({"file": "p.go", "start_line": 4, "end_line": 4, "expression": "x := compute(localPath)"},
                           language="go", revision="revision_A", source=go_indent)
    assert a4b == a4, "indentation-only change must still resolve to the same identity"
    # internal whitespace is semantic: a string-literal spacing change must NOT match
    go_str = "package p\nvar s = \"a  b\"\n"
    try:
        resolve_span({"file": "p.go", "start_line": 2, "end_line": 2, "expression": "var s = \"a b\""}, go_str)
        raise AssertionError("internal (string-literal) whitespace change was wrongly matched")
    except ResolverError:
        pass
    # block-header anchor resolves (if-statement header line)
    guard = resolve_identity({"file": "p.go", "start_line": 5, "end_line": 5, "expression": "if guard(x) {"},
                             language="go", revision="revision_A", source=go)
    assert guard[3] == "*ast.IfStmt", guard
    # multiline expression
    ml = resolve_identity({"file": "p.go", "start_line": 5, "end_line": 7,
                           "expression": "if guard(x) {\nreturn\n}"}, language="go",
                          revision="revision_A", source=go)
    assert ml[3] == "*ast.IfStmt"
    # revision passthrough distinguishes identities
    other = resolve_identity({"file": "p.go", "start_line": 4, "end_line": 4, "expression": "x := compute(localPath)"},
                             language="go", revision="revision_B", source=go)
    assert other != a4 and other[1] == "revision_B"
    # resolve_doc pre-resolves slots so agreement runs with passthrough
    anchor = {"file": "p.go", "start_line": 5, "end_line": 5, "expression": "if guard(x) {"}
    realization = {"state": "present", "anchor": anchor}
    item = {"id": "b", "kind": "behavior", "behavior": {"revision_A": realization}}
    doc = {"items": [item]}
    rd = resolve_doc(doc, language="go", source_provider=lambda rev, f: go)
    ident = rd["items"][0]["behavior"]["revision_A"]["anchor"]["node_identity"]
    assert ident[3] == "*ast.IfStmt"
    print("resolver self-test ok:", {"if_node": guard[3], "distinct_lines": a4 != a8})


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        _self_test()
    else:
        print(__doc__)
