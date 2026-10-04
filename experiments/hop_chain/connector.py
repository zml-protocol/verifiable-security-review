"""The same-object connector (PREREGISTRATION.md §12.1): a graph-level node equivalence,
not a security relation. Given two resolved Go nodes it answers SAME_OBJECT or
NOT_PROVEN_SAME, from the rows of the frozen query queries/go/SameObject.ql.

    uv run python experiments/hop_chain/connector.py calibrate --set dev|cal
    uv run python experiments/hop_chain/connector.py freeze --targets pilot   # plumbing-pilot modules
    uv run python experiments/hop_chain/connector.py freeze --targets eval    # only after the §12 freeze
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "hop_verify"))

import verify

from spike import hops as hoplib

QUERY = HERE / "queries" / "go" / "SameObject.ql"
FROZEN = HERE / "frozen"
RUNS = ROOT / "runs" / "hop_chain" / "connector"
SAME, NOT_PROVEN = "SAME_OBJECT", "NOT_PROVEN_SAME"
MUST_NOT_BE_SAME = ("different", "not_always")
CAL_RESULT = ROOT / "results" / "chain-connector-cal.json"
TARGETS = {"eval": ("caddy-forward-auth", "filebrowser-archive-backslash"), "pilot": ("hopdev-go",)}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Connector:
    """Answers from frozen rows: (file, line, col, kind, variable, def_line, def_col)."""

    def __init__(self, rows: list[list]):
        keys: dict[tuple, set] = {}
        for f, line, col, _, var, dl, dc in rows:
            keys.setdefault((f, line, col), set()).add((f, var, dl, dc))
        # a node with more than one definition key is ambiguous: it never takes part
        self.key = {node: next(iter(ks)) for node, ks in keys.items() if len(ks) == 1}

    def same_object(self, a: tuple, b: tuple) -> str:
        """a, b: node identities ("node", file, line, col) from spike.hops."""
        if a[0] != "node" or b[0] != "node":
            return NOT_PROVEN
        ka, kb = self.key.get(tuple(a[1:])), self.key.get(tuple(b[1:]))
        return SAME if ka is not None and ka == kb else NOT_PROVEN


def load_frozen(fixture: str, revision: str) -> Connector | None:
    path = FROZEN / f"{fixture}.{revision}.same_object.json.gz"
    if not path.exists():
        return None
    return Connector(json.loads(gzip.decompress(path.read_bytes()))["rows"])


def query_rows(db: Path, workdir: Path, language: str) -> list[list]:
    env = {**os.environ, **(verify.reach.go_env() if language == "go" else {})}
    return verify.run_query(db, QUERY, workdir / "same_object.json", env)


# ---- calibration -----------------------------------------------------------------------


def gate() -> list[str]:
    """§12.1: the held-out calibration is a hard precondition of the replication. Empty when
    it ran on the current query and pairs and nothing unsafe was found; never a fallback."""
    if not CAL_RESULT.exists():
        return ["the held-out connector calibration (cal) has not run"]
    r = json.loads(CAL_RESULT.read_text())
    problems = []
    if r.get("set") != "cal":
        problems.append("the calibration result is not the cal set")
    if r.get("query_sha256") != _sha256(QUERY):
        problems.append("SameObject.ql changed after the calibration")
    if r.get("pairs_sha256") != _sha256(HERE / "connector" / "cal.yaml"):
        problems.append("cal.yaml changed after the calibration")
    if r.get("unsafe") != []:
        problems.append(f"CONNECTOR_CALIBRATION_FAILED: unsafe pairs {r.get('unsafe')}")
    return problems


def rows_problems(targets: str) -> list[str]:
    """Every expected frozen connector file exists, is in the manifest, matches its hash, and
    was produced by the current query."""
    path = FROZEN / "manifest.json"
    if not path.exists():
        return ["no connector manifest"]
    manifest = json.loads(path.read_text())
    problems = [] if manifest.get("query_sha256") == _sha256(QUERY) else [
        "connector rows were produced by another query"]
    for fid in TARGETS[targets]:
        for rev in ("base", "head"):
            name = f"{fid}.{rev}.same_object.json.gz"
            entry = manifest["files"].get(name)
            if entry is None or not (FROZEN / name).exists():
                problems.append(f"missing connector rows {name}")
            elif hashlib.sha256(gzip.decompress((FROZEN / name).read_bytes())).hexdigest() \
                    != entry["sha256_json"]:
                problems.append(f"connector rows {name} changed")
    return problems


def calibrate(args: argparse.Namespace) -> None:
    if args.set == "cal" and CAL_RESULT.exists():
        sys.exit("the held-out calibration has already run; it runs once (§12.1)")
    spec = yaml.safe_load((HERE / "connector" / f"{args.set}.yaml").read_text())
    fx = spec["fixture"]
    fixture = {"language": fx["language"], "repo": fx["repo"], "db_build": fx["db_build"],
               "commits": {"base": fx["commit"]}}
    work = RUNS / args.set
    analysis = verify.analyze(fx["id"], fixture, "base", set(), work)
    if analysis["status"] != "ok":
        sys.exit(f"tool failure: {analysis['error'][:500]}")
    connector = Connector(query_rows(work / "db", work, fx["language"]))
    text = verify.source(fixture, "base", fx["file"])
    results, counts = [], {}
    for pair in spec["pairs"]:
        nodes = []
        for line, expr in (pair["a"], pair["b"]):
            at = hoplib.locate(text, {"file": fx["file"], "start_line": line, "end_line": line,
                                      "expression": expr}, byte_columns=True)
            nodes.append(("node", fx["file"], *at))
        state = connector.same_object(*nodes)
        results.append({"id": pair["id"], "truth": pair["truth"], "state": state})
        counts.setdefault(pair["truth"], {SAME: 0, NOT_PROVEN: 0})[state] += 1
    unsafe = [r["id"] for r in results if r["truth"] in MUST_NOT_BE_SAME and r["state"] == SAME]
    same = counts.get("same", {SAME: 0, NOT_PROVEN: 0})
    summary = {"set": args.set, "unsafe": unsafe, "counts": counts,
               "same_coverage": same[SAME] / max(1, same[SAME] + same[NOT_PROVEN]),
               "query_sha256": _sha256(QUERY),
               "pairs_sha256": _sha256(HERE / "connector" / f"{args.set}.yaml"),
               "results": results}
    out = ROOT / "results" / f"chain-connector-{args.set}.json"
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ("unsafe", "counts", "same_coverage")}, indent=1))
    print(f"-> {out.relative_to(ROOT)}")


# ---- freezing rows for the evaluation fixtures --------------------------------------------


def freeze(args: argparse.Namespace) -> None:
    if args.targets == "eval" and (problems := gate()):
        sys.exit("connector gate not passed: " + "; ".join(problems))
    FROZEN.mkdir(parents=True, exist_ok=True)
    path = FROZEN / "manifest.json"
    manifest = json.loads(path.read_text())["files"] if path.exists() else {}
    analysis_root = ROOT / "runs" / "hop_propose" / "analysis"
    frozen_rows = ROOT / "experiments" / "hop_propose" / "frozen"
    for fid in TARGETS[args.targets]:
        for rev in ("base", "head"):
            work = analysis_root / fid / rev
            meta = json.loads(gzip.decompress((frozen_rows / f"{fid}.{rev}.json.gz").read_bytes()))
            rows = sorted(query_rows(work / "db", work, "go"))
            data = json.dumps({"fixture": fid, "revision": rev, "commit": meta["commit"],
                               "rows": rows}, sort_keys=True, separators=(",", ":")).encode()
            path = FROZEN / f"{fid}.{rev}.same_object.json.gz"
            path.write_bytes(gzip.compress(data, mtime=0))
            manifest[path.name] = {"sha256_json": hashlib.sha256(data).hexdigest(), "rows": len(rows)}
            print(fid, rev, len(rows), "object nodes")
    (FROZEN / "manifest.json").write_text(json.dumps(
        {"query_sha256": hashlib.sha256(QUERY.read_bytes()).hexdigest(), "files": manifest},
        indent=2) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calibrate")
    c.add_argument("--set", choices=("dev", "cal"), required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--targets", choices=tuple(TARGETS), required=True)
    args = ap.parse_args()
    {"calibrate": calibrate, "freeze": freeze}[args.cmd](args)


if __name__ == "__main__":
    main()
