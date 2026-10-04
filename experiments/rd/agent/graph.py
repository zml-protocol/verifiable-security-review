"""Recompute and classify a locked RD phase-B graph with the frozen hop rules."""

from __future__ import annotations

import copy
import gzip
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for directory in (HERE, ROOT / "experiments" / "hop_chain"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import chain  # noqa: E402
import connector  # noqa: E402
from spike import hops as hoplib  # noqa: E402

import schema  # noqa: E402
import session  # noqa: E402
import verifiability  # noqa: E402
from source import SourceSurface  # noqa: E402


def load_analysis(paths: dict[str, str]) -> dict[str, dict]:
    return {rev: json.loads(gzip.decompress(Path(path).read_bytes())) for rev, path in paths.items()}


class GraphScorer:
    def __init__(self, *, language: str, repo: str, revisions: dict[str, str],
                 analysis: dict[str, dict]):
        self.language = language
        self.source = SourceSurface(repo, revisions)
        self.analysis = analysis
        self.relations = session.relation_specs(language)
        self.connectors = {
            rev: connector.Connector(doc.get("same_object_rows", [])) if language == "go" else None
            for rev, doc in analysis.items()
        }

    @staticmethod
    def _internal(h: dict) -> dict:
        out = copy.deepcopy(h)
        out["revision"] = "base" if h["revision"] == "revision_A" else "head"
        return out

    def _text(self, internal_revision: str, file: str) -> str | None:
        rev = "revision_A" if internal_revision == "base" else "revision_B"
        try:
            return self.source.text(rev, file)
        except Exception:
            return None

    def resolve_hop(self, h: dict) -> tuple[str, hoplib.Resolved]:
        outward = schema.hop(h, set(self.relations))
        internal = hoplib.normalize(self._internal(outward), self.relations, self.language)
        result = hoplib.resolve(internal, self._text, self.relations,
                                self.analysis[outward["revision"]], self.language)
        state = ("UNSUPPORTED" if outward["relation"] == "unsupported" or
                 not verifiability.verifiable_pair(self.language, outward["relation"]) else
                 hoplib.verdict(internal, result, self.relations,
                                self.analysis[outward["revision"]]))
        return state, result

    def edges(self, b: dict, revision: str) -> tuple[list[dict], list[dict]]:
        edges, mismatches = [], []
        for i, checked in enumerate(b.get("hops") or [], 1):
            h = checked["hop"]
            if h["revision"] != revision:
                continue
            try:
                state, resolved = self.resolve_hop(h)
            except Exception as e:
                mismatches.append({"hop": i, "problem": f"locked hop rejected: {e}"})
                continue
            if state != checked.get("state"):
                mismatches.append({"hop": i, "problem": "stored/recomputed state mismatch",
                                   "stored": checked.get("state"), "recomputed": state})
            if state == "VERIFIED":
                edges.append({"id": f"h{i}", "relation": h["relation"],
                              "a": resolved.node_from, "b": resolved.node_to})
        return edges, mismatches

    def anchor_nodes(self, revision: str, anchor: dict, side: str | None = None) -> set[tuple]:
        """Every frozen relation-role node that the exact anchor can name."""
        text = self.source.text(revision, anchor["file"])
        if text is None:
            return set()
        try:
            at = hoplib.locate(text, anchor, self.language == "go")
        except hoplib.HopError:
            return set()
        roles = []
        for spec in self.relations.values():
            for which in ((side,) if side else ("from", "to")):
                roles.append(spec[which])
        out = set()
        for role in roles:
            node = hoplib.node(self.analysis[revision], role, anchor["file"], at)
            if node is not None:
                out.add(node)
        return out

    @staticmethod
    def _realization_anchor(realization: dict) -> dict:
        return realization["anchor"] if realization["state"] == "present" else realization["context"]

    def _qualifier_anchors(self, requirements: dict, revision: str) -> list[list[dict]]:
        """Each present qualifier contributes one attachment obligation containing its present anchors."""
        obligations = []
        for q in requirements.get("required_qualifiers") or []:
            if q["kind"] == "UNSUPPORTED_REQUIREMENT_TYPE":
                continue
            names = {"guard": ("subject", "predicate"), "config": ("subject", "config"),
                     "dispatch_target": ("call", "target")}[q["kind"]]
            present = [q[name][revision]["anchor"] for name in names
                       if q[name][revision]["state"] == "present"]
            if present:
                obligations.append(present)
        return obligations

    def classify_revision(self, requirements: dict, b: dict, revision: str) -> dict:
        entry_r, behavior_r = requirements["entry"][revision], requirements["behavior"][revision]
        edges, mismatches = self.edges(b, revision)
        if entry_r["state"] == "absent" or behavior_r["state"] == "absent":
            return {"class": "NOT_APPLICABLE", "verified_edges": len(edges),
                    "harness_mismatches": mismatches}
        starts = self.anchor_nodes(revision, entry_r["anchor"], "from")
        terminals = self.anchor_nodes(revision, behavior_r["anchor"], "to")
        conn = self.connectors[revision]
        same = (lambda a, b: conn.same_object(a, b) == connector.SAME) if conn else None
        paths = []
        for terminal in terminals:
            paths += chain.paths(edges, lambda node, s=starts: any(
                chain.continues(start, node, same) for start in s), terminal, same)

        obligations = self._qualifier_anchors(requirements, revision)

        def attached(path: list[dict]) -> bool:
            nodes = [node for edge in path for node in (edge["a"], edge["b"])]
            for anchors in obligations:
                # Every present anchor slot of a locked qualifier must name a node on the same path.
                for anchor in anchors:
                    candidates = self.anchor_nodes(revision, anchor)
                    if not any(any(n == c or (same and n[0] == c[0] == "node" and same(n, c))
                                       for n in nodes) for c in candidates):
                        return False
            return True

        good = [path for path in paths if attached(path)]
        if good:
            klass, length = "FULL_CHAIN", min(map(len, good))
        elif paths:
            klass, length = "QUALIFIER_GAP", min(map(len, paths))
        elif edges:
            suffix = []
            for terminal in terminals:
                suffix += chain.paths(edges, lambda _: True, terminal, same)
            if suffix:
                klass, length = "ENTRY_GAP", None
            else:
                klass, length = "INTERNAL_GAP", None
        else:
            klass, length = "NO_EVIDENCE", None
        return {"class": klass, "length": length, "verified_edges": len(edges),
                "entry_node_candidates": len(starts), "terminal_node_candidates": len(terminals),
                "qualifier_obligations": len(obligations), "harness_mismatches": mismatches}

    def classify(self, a: dict, b: dict) -> dict:
        rows = {rev: self.classify_revision(a["requirements"], b, rev) for rev in schema.REVISIONS}
        required = [row for row in rows.values() if row["class"] != "NOT_APPLICABLE"]
        return {"revisions": rows,
                "full_chain": bool(required) and all(row["class"] == "FULL_CHAIN" for row in required),
                "harness_mismatches": [m for row in rows.values() for m in row["harness_mismatches"]]}
