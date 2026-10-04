"""Chain classification (PREREGISTRATION.md §12.2). Pure functions over resolved edges.

An edge is a locked hop with a supported relation that the frozen verifier judges VERIFIED;
`unsupported` and UNVERIFIED hops are never edges. Endpoints are spike.hops node identities:
("node", file, line, col) or ("inside", file, first, last) for a function.

After an edge ending at b, an edge starting at c continues the chain iff b == c; or b is a
function and c is a node inside it; or (Go) the frozen same-object connector proves that b
and c name the same object. Paths are node-simple: apart from the joint where an edge meets
the previous one, no node (or node proven to be the same object) is visited twice. At most
MAX_EDGES edges.
"""

from __future__ import annotations

from collections.abc import Callable

MAX_EDGES = 12
QUALIFIER = "guard_property"
CLASSES = ("FULL_CHAIN", "QUALIFIER_GAP", "ENTRY_GAP", "INTERNAL_GAP", "NO_EVIDENCE")

SameObject = Callable[[tuple, tuple], bool] | None


def continues(b: tuple, c: tuple, same: SameObject) -> bool:
    if b == c:
        return True
    if b[0] == "inside" and c[0] == "node" and c[1] == b[1] and b[2] <= c[2] <= b[3]:
        return True
    return same is not None and b[0] == "node" and c[0] == "node" and same(b, c)


def _same_place(x: tuple, y: tuple, same: SameObject) -> bool:
    return x == y or (same is not None and x[0] == "node" and y[0] == "node" and same(x, y))


def paths(edges: list[dict], starts: Callable[[tuple], bool], terminal: tuple,
          same: SameObject) -> list[list[dict]]:
    """Every node-simple path of non-qualifier edges whose first edge starts where `starts`
    allows and whose last edge ends exactly at `terminal`."""
    main = [e for e in edges if e["relation"] != QUALIFIER]
    found: list[list[dict]] = []

    def walk(path: list[dict], seen: list[tuple]) -> None:
        if path[-1]["b"] == terminal:
            found.append(list(path))
        if len(path) == MAX_EDGES:
            return
        for e in main:
            if not continues(path[-1]["b"], e["a"], same):
                continue
            # the start may only meet the previous end (the joint); the end must be new
            earlier = seen[:-1]
            if any(_same_place(e["a"], x, same) for x in earlier):
                continue
            if any(_same_place(e["b"], x, same) for x in [*seen, e["a"]]):
                continue
            walk([*path, e], [*seen, e["a"], e["b"]])

    for e in main:
        if starts(e["a"]) and not _same_place(e["a"], e["b"], same):
            walk([e], [e["a"], e["b"]])
    return found


def qualified(path: list[dict], edges: list[dict], same: SameObject) -> bool:
    """A VERIFIED guard edge ends on a node of the path (or on the same object as one)."""
    on_path = [n for e in path for n in (e["a"], e["b"])]
    return any(g["b"] == n or (same is not None and n[0] == "node" and g["b"][0] == "node"
                               and same(g["b"], n))
               for g in edges if g["relation"] == QUALIFIER for n in on_path)


def classify(edges: list[dict], entry: tuple, terminal: tuple, needs_qualifier: bool,
             same: SameObject) -> dict:
    """One revision of one submission -> its chain class (first that applies, §12.2)."""
    full = paths(edges, lambda a: continues(entry, a, same), terminal, same)
    good = [p for p in full if not needs_qualifier or qualified(p, edges, same)]
    if good:
        return {"class": "FULL_CHAIN", "length": min(map(len, good))}
    if full:
        return {"class": "QUALIFIER_GAP", "length": min(map(len, full))}
    suffixes = paths(edges, lambda a: True, terminal, same)
    if suffixes:
        # the longest verified suffix: how much of the way back from the terminal is covered
        return {"class": "ENTRY_GAP", "length": None,
                "longest_suffix_edges": max(map(len, suffixes)),
                "qualified": (not needs_qualifier) or any(qualified(p, edges, same) for p in suffixes)}
    if edges:
        prefix = any(continues(entry, e["a"], same) for e in edges if e["relation"] != QUALIFIER)
        return {"class": "INTERNAL_GAP", "length": None, "entry_prefix": prefix}
    return {"class": "NO_EVIDENCE", "length": None}
