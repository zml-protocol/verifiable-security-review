"""Typed hops (PREREGISTRATION.md §10.1, §11): anchors, node shapes, node identities and
verdicts read from frozen verifier output.

Everything here is a pure function of source text, the relation spec
(experiments/hop_verify/relations.yaml) and one revision's frozen analysis: the rows the
frozen P-Hybrid-1 queries produced, `shapes` as (kind, file, start_line, start_col,
end_line) and per relation `rows` as (from_file, from_line, from_col, to_file, t1, t2).
The verdict logic reproduces experiments/hop_verify/verify.py `judge` (a test holds them
equal on every §10 hop); nothing here runs CodeQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SIDES = ("base", "head")
UNSUPPORTED = "unsupported"
HOP_KEYS = {"revision", "relation", "from", "to"}
ENDPOINT_KEYS = {"file", "start_line", "end_line", "expression"}

Anchor = tuple[int, int]


class HopError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def locate(text: str, ep: dict, byte_columns: bool) -> Anchor:
    """Where `ep`'s expression starts inside its span: (line, column), both 1-based.

    Whitespace runs (line breaks included) compare as one space; the expression must occur
    exactly once in the span. Go columns count bytes, Python columns characters."""
    lines = text.splitlines()
    lo, hi = ep["start_line"], ep["end_line"]
    if not 1 <= lo <= hi <= len(lines):
        raise HopError("anchor", f"span {lo}-{hi} is outside {ep['file']} ({len(lines)} lines)")
    chars: list[str] = []
    where: list[Anchor | None] = []
    space = False
    for n in range(lo, hi + 1):
        col = 1
        for ch in lines[n - 1]:
            if ch.isspace():
                space = bool(chars)
            else:
                if space:
                    chars.append(" ")
                    where.append(None)
                    space = False
                chars.append(ch)
                where.append((n, col))
            col += len(ch.encode()) if byte_columns else 1
        space = bool(chars)
    norm, expr = "".join(chars), " ".join(ep["expression"].split())
    starts = [i for i in range(len(norm)) if norm.startswith(expr, i)] if expr else []
    if len(starts) != 1:
        raise HopError(
            "anchor", f"the expression occurs {len(starts)} times in {ep['file']}:{lo}-{hi} "
            "(it must occur exactly once)")
    found = where[starts[0]]
    assert found is not None  # an expression never starts with a space
    return found


def normalize(hop: Any, relations: dict, language: str) -> dict:
    """Check a hop's schema and return it in canonical form (no id)."""
    if not isinstance(hop, dict) or set(hop) != HOP_KEYS:
        raise HopError("schema", f"a hop has exactly the keys {sorted(HOP_KEYS)}")
    if hop["revision"] not in SIDES:
        raise HopError("schema", "revision must be 'base' or 'head'")
    rel = hop["relation"]
    applicable = [n for n, r in relations.items() if r["language"] == language]
    if rel != UNSUPPORTED and rel not in applicable:
        raise HopError("schema", f"relation must be one of {[*applicable, UNSUPPORTED]}")
    out = {"revision": hop["revision"], "relation": rel}
    for side in ("from", "to"):
        ep = hop[side]
        if not isinstance(ep, dict) or set(ep) != ENDPOINT_KEYS:
            raise HopError("schema", f"'{side}' has exactly the keys {sorted(ENDPOINT_KEYS)}")
        lo, hi = ep["start_line"], ep["end_line"]
        if not (isinstance(lo, int) and isinstance(hi, int) and 1 <= lo <= hi):
            raise HopError("schema", f"'{side}' needs integer lines with 1 <= start_line <= end_line")
        if not isinstance(ep["file"], str) or not isinstance(ep["expression"], str):
            raise HopError("schema", f"'{side}' file and expression are strings")
        if not ep["expression"].split():
            raise HopError("schema", f"'{side}' expression is empty")
        out[side] = {"file": ep["file"], "start_line": lo, "end_line": hi,
                     "expression": " ".join(ep["expression"].split())}
    return out


def key(hop: dict) -> tuple:
    """Duplicate detection: two hops with the same key are the same claim."""
    return (hop["revision"], hop["relation"],
            *(tuple(hop[s][k] for k in ("file", "start_line", "end_line", "expression"))
              for s in ("from", "to")))


# ---- node shapes and identities -------------------------------------------------------


def _innermost(analysis: dict, kinds: set[str], file: str, line: int) -> tuple | None:
    rows = [r for r in analysis["shapes"]
            if r[0] in kinds and r[1] == file and r[2] <= line <= r[4]]
    if not rows:
        return None
    _, f, sl, _, el = max(rows, key=lambda r: (r[2], -r[4]))
    return ("inside", f, sl, el)


def node(analysis: dict, role: dict, file: str, at: Anchor) -> tuple | None:
    """The node an endpoint names under a relation role, or None when the claimed revision's
    syntax tree has no node of an allowed kind there (a closed-world fact)."""
    kinds = set(role["kinds"])
    if role["role"] == "inside":
        return _innermost(analysis, kinds, file, at[0])
    if any(r[0] in kinds and r[1] == file and (r[2], r[3]) == at for r in analysis["shapes"]):
        return ("node", file, *at)
    return None


def extracted(analysis: dict, file: str) -> bool:
    return any(r[0] == "file" and r[1] == file for r in analysis["shapes"])


@dataclass(frozen=True)
class Resolved:
    """One hop resolved against its revision: anchors, and the nodes it names (None for an
    unsupported relation, which has no node roles)."""

    anchor_from: Anchor
    anchor_to: Anchor
    node_from: tuple | None
    node_to: tuple | None


def resolve(hop: dict, text_of, relations: dict, analysis: dict, language: str) -> Resolved:
    """Anchor and shape-check a canonical hop. `text_of(revision, file)` returns the file's
    text at that revision or None. Raises HopError for anything the runtime rejects."""
    byte_columns = language == "go"
    anchors = []
    for side in ("from", "to"):
        ep = hop[side]
        text = text_of(hop["revision"], ep["file"])
        if text is None:
            raise HopError("anchor", f"{ep['file']} does not exist in revision {hop['revision']}")
        anchors.append(locate(text, ep, byte_columns))
    if hop["relation"] == UNSUPPORTED:
        return Resolved(anchors[0], anchors[1], None, None)
    spec = relations[hop["relation"]]
    nodes, bad = [], []
    for side, at in zip(("from", "to"), anchors, strict=True):
        if not extracted(analysis, hop[side]["file"]):
            raise HopError("not_analyzed", f"{hop[side]['file']} is outside the analyzed code")
        found = node(analysis, spec[side], hop[side]["file"], at)
        if found is None:
            kinds = " or ".join(spec[side]["kinds"])
            bad.append(f"'{side}' must lie inside a {kinds}" if spec[side]["role"] == "inside"
                       else f"'{side}' must name a {kinds}: its expression has to start "
                       "exactly where that code starts")
        nodes.append(found)
    if bad:
        raise HopError("shape", "; ".join(bad))
    return Resolved(anchors[0], anchors[1], nodes[0], nodes[1])


def verdict(hop: dict, resolved: Resolved, relations: dict, analysis: dict) -> str:
    """VERIFIED when a frozen relation row links the two endpoints, else UNVERIFIED."""
    if hop["relation"] == UNSUPPORTED:
        return "UNVERIFIED"
    inside = relations[hop["relation"]]["to"]["role"] == "inside"
    f, t = hop["from"]["file"], hop["to"]["file"]
    for ff, fl, fc, tf, t1, t2 in analysis["rows"].get(hop["relation"], []):
        if ff != f or (fl, fc) != resolved.anchor_from or tf != t:
            continue
        if inside and t1 <= resolved.anchor_to[0] <= t2:
            return "VERIFIED"
        if not inside and (t1, t2) == resolved.anchor_to:
            return "VERIFIED"
    return "UNVERIFIED"


def located(hop: dict, resolved: Resolved, golden: dict, golden_resolved: Resolved,
            relations: dict, analysis: dict) -> bool:
    """Same place as a golden hop, whatever relation the hop was typed with: the same
    revision, `from` starting at the golden `from` node, and `to` at the golden `to` node
    (for an `inside` golden role: inside the same innermost function)."""
    if hop["revision"] != golden["revision"] or hop["from"]["file"] != golden["from"]["file"]:
        return False
    if resolved.anchor_from != golden_resolved.anchor_from:
        return False
    role = relations[golden["relation"]]["to"]
    if role["role"] == "inside":
        mine = _innermost(analysis, set(role["kinds"]), hop["to"]["file"], resolved.anchor_to[0])
        return mine is not None and mine == golden_resolved.node_to
    return hop["to"]["file"] == golden["to"]["file"] and resolved.anchor_to == golden_resolved.anchor_to


def matches(hop: dict, resolved: Resolved, golden: dict, golden_resolved: Resolved,
            relations: dict, analysis: dict) -> bool:
    """A typed match: located, and typed with the golden hop's relation."""
    return hop["relation"] == golden["relation"] and located(
        hop, resolved, golden, golden_resolved, relations, analysis)
