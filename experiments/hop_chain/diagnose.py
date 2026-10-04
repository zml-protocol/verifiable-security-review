"""P-Hybrid-3 design diagnostic (PREREGISTRATION.md §12.0). DESIGN INFORMATION, NOT A RESULT.

    uv run python experiments/hop_chain/diagnose.py

Do the frozen P-Hybrid-2 INITIAL submissions (shared by both arms; the arms' finals are
deliberately not read) already form fully VERIFIED chains from an entry to a terminal?
No LLM call, no rescoring: every P-Hybrid-2 verdict stands.

Rules, committed before this script first ran:
- One graph per submission and revision. Edges: locked hops with a supported relation that
  the frozen verifier judges VERIFIED; `unsupported` and UNVERIFIED hops are never edges.
  Endpoints are the frozen node identities of spike.hops: ("node", file, line, col) or
  ("inside", file, first, last) for a function.
- Connector C1 (node identity): after an edge ending at b, an edge starting at c continues
  the chain iff b == c, or b is a function and c is a node inside it.
- Connector C2 (C1 plus same object; Go; heuristic): also iff b and c name the same local
  variable v with the same reaching definition: b is a field store `v.f = ...`, and c is the
  definition of v that reaches it or another field store on v reached by the same
  definition. Variables, definitions and function boundaries are read from the source
  text (design information only).
- Endpoints G: from the golden hops of the fixture and revision minus the guard_property
  hops, the chain order is recovered with C1; entry = the first hop's `from` node, terminal
  = the last hop's `to` identity. A path must start at the entry (or, under C2, at the
  same object) and end exactly at the terminal.
- Qualifier Q: when the golden hops contain guard_property hops, a complete chain also
  needs a VERIFIED guard_property edge whose `to` lies on the path (C2: or names the same
  object as a node on it).
- Simple paths only, at most 12 edges.
Spike P endpoints (endpoints.yaml) are checked for expressibility by hand in §12.0.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "hop_propose"))

import propose_score as S  # noqa: E402  (frozen matcher, frozen analyses, P-Hybrid-2 runs)

from spike import hops as hoplib  # noqa: E402

MAX_EDGES = 12
OUT = ROOT / "runs" / "hop_chain" / "diagnostic.json"
QUALIFIER = "guard_property"
_IDENT = r"[A-Za-z_]\w*"


# ---- connectors ------------------------------------------------------------------------


class Objects:
    """C2: which local variable a Go node names, and the definition that reaches it."""

    def __init__(self, m: S.Matcher, revision: str):
        self.m, self.revision = m, revision
        self.defs = [r for r in m.analysis[revision]["shapes"] if r[0] == "definition"]

    def _line(self, file: str, line: int) -> str:
        text = self.m.text_of(self.revision, file) or ""
        lines = text.splitlines()
        return lines[line - 1] if 0 < line <= len(lines) else ""

    def store_var(self, node: tuple) -> str | None:
        if node[0] != "node":
            return None
        _, file, line, col = node
        m = re.match(rf"\s*({_IDENT})\.{_IDENT}\s*=[^=]", self._line(file, line)[col - 1:])
        return m[1] if m else None

    def def_vars(self, file: str, line: int, col: int) -> list[str]:
        rest = self._line(file, line)[col - 1:]
        m = re.match(rf"\s*(?:var\s+)?({_IDENT}(?:\s*,\s*{_IDENT})*)\s*(?::=|=[^=]|\s+\S)", rest)
        return [v.strip() for v in m[1].split(",")] if m else []

    def func_start(self, file: str, line: int) -> int:
        text = (self.m.text_of(self.revision, file) or "").splitlines()
        for n in range(line, 0, -1):
            if text[n - 1].startswith("func "):
                return n
        return 1

    def reaching(self, v: str, file: str, line: int) -> tuple | None:
        lo = self.func_start(file, line)
        best = None
        for _, f, sl, sc, _ in self.defs:
            if f == file and lo <= sl < line and v in self.def_vars(f, sl, sc):
                if best is None or sl > best[2]:
                    best = ("node", f, sl, sc)
        return best

    def object_of(self, node: tuple) -> tuple | None:
        """(variable, reaching definition) the node stands for, if any."""
        if node[0] != "node":
            return None
        v = self.store_var(node)
        if v:
            return (v, self.reaching(v, node[1], node[2]))
        vs = self.def_vars(node[1], node[2], node[3])
        if len(vs) == 1 and node in [("node", f, sl, sc) for _, f, sl, sc, _ in self.defs]:
            return (vs[0], node)
        return None


def continues(b: tuple, c: tuple, objects: Objects | None) -> bool:
    if b == c:
        return True
    if b[0] == "inside" and c[0] == "node" and c[1] == b[1] and b[2] <= c[2] <= b[3]:
        return True
    if objects is not None:
        ob, oc = objects.object_of(b), objects.object_of(c)
        return ob is not None and ob[1] is not None and ob == oc
    return False


# ---- graphs and paths --------------------------------------------------------------------


def edges_of(m: S.Matcher, hops: list[dict], revision: str) -> list[dict]:
    out = []
    for h in hops or []:
        if h["revision"] != revision or h["relation"] == hoplib.UNSUPPORTED:
            continue
        c = {k: h[k] for k in ("revision", "relation", "from", "to")}
        res = m.resolve(c)
        if hoplib.verdict(c, res, S.R.RELATIONS, m.analysis[revision]) == "VERIFIED":
            out.append({"id": h["id"], "relation": h["relation"], "a": res.node_from,
                        "b": res.node_to})
    return out


def golden_ends(m: S.Matcher, revision: str) -> dict:
    gs = [g for g in m.golden if g["revision"] == revision]
    main = [g for g in gs if g["relation"] != QUALIFIER]
    res = m.golden_resolved
    first = [g for g in main
             if not any(continues(res[o["id"]].node_to, res[g["id"]].node_from, None)
                        for o in main if o is not g)]
    last = [g for g in main
            if not any(continues(res[g["id"]].node_to, res[o["id"]].node_from, None)
                       for o in main if o is not g)]
    assert len(first) == 1 and len(last) == 1, (m.fixture, revision)
    return {"entry": res[first[0]["id"]].node_from, "terminal": res[last[0]["id"]].node_to,
            "qualified": any(g["relation"] == QUALIFIER for g in gs), "golden_edges": len(main)}


def chains(edges: list[dict], ends: dict, objects: Objects | None) -> list[list[dict]]:
    main = [e for e in edges if e["relation"] != QUALIFIER]
    found: list[list[dict]] = []

    def walk(path: list[dict]) -> None:
        if path[-1]["b"] == ends["terminal"]:
            found.append(list(path))
        if len(path) == MAX_EDGES:
            return
        for e in main:
            if e not in path and continues(path[-1]["b"], e["a"], objects):
                walk([*path, e])

    for e in main:
        if continues(ends["entry"], e["a"], objects):
            walk([e])
    return found


def qualified(path: list[dict], edges: list[dict], objects: Objects | None) -> bool:
    nodes = [n for e in path for n in (e["a"], e["b"])]
    for g in (e for e in edges if e["relation"] == QUALIFIER):
        if any(g["b"] == n or (objects is not None and continues(g["b"], n, objects)
                               and n[0] == "node") for n in nodes):
            return True
    return False


def complete(edges: list[dict], ends: dict, objects: Objects | None) -> dict:
    paths = chains(edges, ends, objects)
    if ends["qualified"]:
        paths = [p for p in paths if qualified(p, edges, objects)]
    return {"complete": bool(paths),
            "shortest": min((len(p) for p in paths), default=None)}


def main() -> None:
    scored = json.loads((ROOT / "results" / "p-hybrid-2-scores.json").read_text())
    matchers: dict[str, S.Matcher] = {}
    rows = []
    for pair in scored["pairs"]:
        fixture = pair["fixture"]
        m = matchers.setdefault(fixture, S.Matcher(fixture, pilot=False))
        block = S.R.runs_root(False) / fixture / f"r{pair['repeat']}"
        initial = S.state_of(block / "initial")["initial"]
        for revision in ("base", "head"):
            ends = golden_ends(m, revision)
            edges = edges_of(m, initial, revision)
            objects = Objects(m, revision) if m.entry["language"] == "go" else None
            rows.append({
                "block": pair["block"], "fixture": fixture, "revision": revision,
                "entry": ends["entry"], "terminal": ends["terminal"],
                "qualified": ends["qualified"], "verified_edges": len(edges),
                "C1": complete(edges, ends, None),
                "C2": complete(edges, ends, objects) if objects else complete(edges, ends, None),
                "golden_strict": sorted(g for g in pair["initial"]["verified_golden"]
                                        if any(x["id"] == g and x["revision"] == revision
                                               for x in m.golden)),
            })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1))
    for r in rows:
        print(f"{r['block']:34} {r['revision']:4} edges={r['verified_edges']:2} "
              f"C1={'Y' if r['C1']['complete'] else '-'}({r['C1']['shortest']}) "
              f"C2={'Y' if r['C2']['complete'] else '-'}({r['C2']['shortest']}) "
              f"golden_strict={r['golden_strict']}")


if __name__ == "__main__":
    main()
