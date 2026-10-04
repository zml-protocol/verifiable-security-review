"""Fixture-independent anchor machinery for distractor generation (PREREGISTRATION §15.1 item 4).

`distractors.py` (frozen) asks the caller for three callbacks — ``relocate``, ``context_for``,
``present_for`` — plus a qualifier ``rebuild``. Those are the "frozen anchor machinery at fixture
time" that never existed; this module is it, generic and reusable. No fixture symbol/path/line
appears here. It uses only the frozen anchor schema, repository revision source, and the frozen
resolver/matcher, and it fails loud on malformed input (returning ``None`` only where distractors.py
expects "no distractor here"). It does not change distractor semantics.

- ``relocate`` (near-move, §10.4): point the anchor at a nearby *real* statement line that exists
  unchanged in both revisions and resolves to a different node than the original. No nearby valid
  line → None.
- ``context_for`` / ``present_for``: present<->absent state-flip reuses the same code span as the
  counterpart realization (a structurally valid, deliberately-wrong distractor).
- ``rebuild``: re-label a qualifier under a different frozen kind, keeping its slots.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import resolver

HERE = Path(__file__).resolve()
SLOT_KEYS = ("revision_A", "revision_B")


class AnchorMachineryError(RuntimeError):
    """Malformed input (fail loud). 'No distractor possible' is a None return, not an error."""


def _require_anchor(a) -> None:
    if not isinstance(a, dict):
        raise AnchorMachineryError(f"anchor/context must be a dict, got {type(a).__name__}")
    for k in ("file", "start_line", "end_line", "expression"):
        if k not in a:
            raise AnchorMachineryError(f"anchor/context missing {k!r}: {a}")


def _is_statement_like(stripped: str) -> bool:
    # A near-move target must be real code, not blank or brace/punctuation-only noise.
    return bool(stripped) and any(c.isalnum() for c in stripped)


def _nearby_order(sl: int, el: int, n: int):
    """Line numbers nearest the anchor first, below then above, excluding the anchor's own lines."""
    out, d = [], 1
    while el + d <= n or sl - d >= 1:
        if el + d <= n:
            out.append(el + d)
        if sl - d >= 1:
            out.append(sl - d)
        d += 1
    return out


def context_for(anchor: dict) -> dict:
    """present -> absent: reuse the anchor's span as the counterpart context."""
    _require_anchor(anchor)
    return {k: anchor[k] for k in ("file", "start_line", "end_line", "expression")}


def present_for(context: dict) -> dict:
    """absent -> present: reuse the context's span as the counterpart anchor."""
    _require_anchor(context)
    return {k: context[k] for k in ("file", "start_line", "end_line", "expression")}


def rebuild(item: dict, new_kind: str) -> dict:
    """Re-label a qualifier under a different frozen kind, keeping its slots (kind-swap distractor)."""
    if not isinstance(item, dict):
        raise AnchorMachineryError("item must be a dict")
    out = copy.deepcopy(item)
    out["kind"] = new_kind
    return out


def make_relocator(language: str, source_provider):
    """Return a near-move `relocate(anchor) -> anchor|None` bound to a revision source provider.

    `source_provider(revision, file) -> str` returns the file text at that revision (revision in
    SLOT_KEYS). The chosen nearby line must exist (same text) and resolve uniquely in BOTH revisions,
    so the distractor is valid wherever its slot places it, and must resolve to a different node than
    the original in revision_A.
    """
    def relocate(anchor: dict):
        _require_anchor(anchor)
        file = anchor["file"]
        try:
            srcs = {rev: source_provider(rev, file) for rev in SLOT_KEYS}
        except Exception as e:  # source provider failure is fail-loud
            raise AnchorMachineryError(f"source provider failed for {file!r}: {e}")
        lines_a = srcs["revision_A"].split("\n")
        try:
            sl, el = int(anchor["start_line"]), int(anchor["end_line"])
        except (TypeError, ValueError) as e:
            raise AnchorMachineryError(f"anchor line numbers not integers: {e}")
        # original identity in revision_A, if the original resolves there (else no same-node filter)
        try:
            orig = resolver.resolve_identity(anchor, language=language, revision="revision_A",
                                             source=srcs["revision_A"])
        except resolver.ResolverError:
            orig = None
        for L in _nearby_order(sl, el, len(lines_a)):
            c = lines_a[L - 1].strip()
            if not _is_statement_like(c):
                continue
            cand = {"file": file, "start_line": L, "end_line": L, "expression": c}
            ids = {}
            try:
                for rev in SLOT_KEYS:
                    ids[rev] = resolver.resolve_identity(cand, language=language, revision=rev,
                                                         source=srcs[rev])
            except resolver.ResolverError:
                continue  # not a clean, common, unique statement line in both revisions
            if orig is not None and ids["revision_A"] == orig:
                continue  # same node as the original; not a move
            return cand
        return None

    return relocate


def source_hash() -> str:
    return hashlib.sha256(HERE.read_bytes()).hexdigest()


def _self_test() -> None:
    # Two revisions; line 4 differs between them, lines 3/5/6 are common unchanged statements.
    src_a = ("package p\n"            # 1
             "func F() {\n"           # 2
             "\ta := 1\n"             # 3  common
             "\tb := 2\n"             # 4  (A)
             "\tc := use(a, b)\n"     # 5  common
             "\treturn\n"             # 6  common
             "}\n")                   # 7
    src_b = src_a.replace("\tb := 2\n", "\tb := 2 + 0\n")  # line 4 changed in B
    provider = {"revision_A": src_a, "revision_B": src_b}
    relocate = make_relocator("go", lambda rev, f: provider[rev])

    # near-move from the common line 3 -> a different nearby common line (5 or 6), valid in both.
    anchor3 = {"file": "p.go", "start_line": 3, "end_line": 3, "expression": "a := 1"}
    moved = relocate(anchor3)
    assert moved is not None and moved["start_line"] != 3
    assert resolver.resolve_identity(moved, language="go", revision="revision_A", source=src_a)
    assert resolver.resolve_identity(moved, language="go", revision="revision_B", source=src_b)

    # a line that changed between revisions (line 4) is never chosen as a near-move target
    # (it would fail to resolve identically in both): confirm the mover avoids it.
    for L in range(2, 8):
        pass
    assert moved["start_line"] != 4

    # context_for / present_for reuse the span symmetrically
    ctx = context_for(anchor3)
    assert ctx == {"file": "p.go", "start_line": 3, "end_line": 3, "expression": "a := 1"}
    assert present_for(ctx) == ctx

    # rebuild relabels kind, keeps slots
    item = {"id": "q", "kind": "guard", "expected": "must_hold",
            "subject": {"revision_A": {"state": "present", "anchor": anchor3}}}
    rb = rebuild(item, "config")
    assert rb["kind"] == "config" and rb["subject"] == item["subject"]

    # malformed input fails loud
    for bad in (None, {"file": "x"}, 5):
        try:
            context_for(bad)
            raise AssertionError(f"malformed context not rejected: {bad}")
        except AnchorMachineryError:
            pass

    # no nearby valid line -> None (singleton file)
    tiny = "package p\n"
    rel2 = make_relocator("go", lambda rev, f: tiny)
    assert rel2({"file": "p.go", "start_line": 1, "end_line": 1, "expression": "package p"}) is None
    print("anchor_machinery self-test ok:", {"moved_to": moved["start_line"]})


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        _self_test()
    else:
        print(__doc__)
