"""Chain replication scoring (PREREGISTRATION.md §12.2). Descriptive: per fixture, how many
blocks' one-shot submissions form a FULL_CHAIN at both revisions, with 95% Wilson intervals,
and the class of every revision. No success threshold.

    uv run python experiments/hop_chain/replicate_score.py --out results/chain-replication.json
    uv run python experiments/hop_chain/replicate_score.py --pilot --out runs/hop_chain/pilot.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "hop_propose"))
sys.path.insert(0, str(HERE))

import chain
import connector as C
import propose_score as S
import replicate as RP

from spike import hops as hoplib

MIN_VALID_PER_FIXTURE = 8


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def anchors(pilot: bool) -> dict:
    name = "pilot_anchors.yaml" if pilot else "anchors.yaml"
    raw = yaml.safe_load((HERE / name).read_text())
    return {f: {rev: {"entry": tuple(a["entry"]), "terminal": tuple(a["terminal"]),
                      "needs_qualifier": a["needs_qualifier"]} for rev, a in revs.items()}
            for f, revs in raw.items()}


def revision_edges(m: S.Matcher, hops: list[dict], revision: str) -> tuple[list[dict], list[str]]:
    edges, rejected = [], []
    for h in hops or []:
        if h["revision"] != revision or h["relation"] == hoplib.UNSUPPORTED:
            continue
        c = {k: h[k] for k in ("revision", "relation", "from", "to")}
        try:
            res = m.resolve(c)
        except hoplib.HopError:
            rejected.append(h["id"])  # runtime and scorer disagree: a harness violation
            continue
        if hoplib.verdict(c, res, S.R.RELATIONS, m.analysis[revision]) == "VERIFIED":
            edges.append({"id": h["id"], "relation": h["relation"], "a": res.node_from,
                          "b": res.node_to})
    return edges, rejected


def score(pilot: bool) -> dict:
    # §12.1: the connector gate and every expected connector file are preconditions of any
    # formal rate; there is no fallback to another connector
    problems = C.rows_problems("pilot" if pilot else "eval") + ([] if pilot else C.gate())
    if problems:
        status = ("CONNECTOR_CALIBRATION_FAILED"
                  if any(x.startswith("CONNECTOR_CALIBRATION_FAILED") for x in problems)
                  else "PROTOCOL_INVALID")
        return {"protocol": RP.PROTOCOL, "pilot": pilot, "status": status, "problems": problems}
    root = RP.runs_root(pilot)
    fixtures = sorted(S.R.CASES["pilot" if pilot else "eval"])
    blocks = [(f, 0) for f in fixtures] if pilot else S.R.read_order(HERE / "order.txt")
    anchor = anchors(pilot)
    matchers: dict[str, S.Matcher] = {}
    rows, invalid = [], []
    harness = {"context_leak": {}, "foreign_tools": {}, "harness_errors": 0,
               "locked_hop_rejected": {}}
    for fixture, repeat in blocks:
        run_dir = root / fixture / f"r{repeat}"
        name = f"{fixture}/r{repeat}"
        validity = S.R.classify(run_dir) if (run_dir / "meta.json").exists() else ("MISSING", "not_run")
        if validity[0] != "VALID":
            invalid.append({"block": name, "validity": validity})
            continue
        if found := S.leaks(run_dir, run_dir):
            harness["context_leak"][name] = found
        if tools := S.foreign_tools(run_dir):
            harness["foreign_tools"][name] = tools
        harness["harness_errors"] += S.harness_errors(run_dir)
        m = matchers.setdefault(fixture, S.Matcher(fixture, pilot))
        hops = S.state_of(run_dir)["initial"] or []
        per_revision = {}
        for rev in ("base", "head"):
            edges, rejected = revision_edges(m, hops, rev)
            if rejected:
                harness["locked_hop_rejected"][f"{name}/{rev}"] = rejected
            conn = C.load_frozen(fixture, rev) if m.entry["language"] == "go" else None
            if m.entry["language"] == "go" and conn is None:  # excluded by the check above
                raise RuntimeError(f"no connector rows for {fixture} {rev}")
            same = (lambda a, b, c=conn: c.same_object(a, b) == C.SAME) if conn else None
            a = anchor[fixture][rev]
            per_revision[rev] = {**chain.classify(edges, a["entry"], a["terminal"],
                                                  a["needs_qualifier"], same),
                                 "verified_edges": len(edges)}
        sub = m.submission(hops)
        rows.append({"block": name, "fixture": fixture, "repeat": repeat,
                     "revisions": per_revision,
                     "full_chain": all(r["class"] == "FULL_CHAIN" for r in per_revision.values()),
                     "hops": sub["n"], "unsupported": sub["unsupported"],
                     "novel": sum(1 for h in sub["hops"] if h["unit"] is not None),
                     "golden_verified": sub["verified_golden"],
                     "cost_usd": json.loads((run_dir / "meta.json").read_text()).get("cost_usd")})
    harness["frozen_verifier_rows_intact"] = S.frozen_ok()
    harness["frozen_connector_rows_intact"] = not C.rows_problems("pilot" if pilot else "eval")
    harness_ok = not (harness["context_leak"] or harness["foreign_tools"] or harness["harness_errors"]
                      or harness["locked_hop_rejected"]) and harness["frozen_verifier_rows_intact"] \
        and harness["frozen_connector_rows_intact"]
    per_fixture = {}
    for f in fixtures:
        rs = [r for r in rows if r["fixture"] == f]
        k = sum(r["full_chain"] for r in rs)
        classes = {c: sum(r["revisions"][rev]["class"] == c for r in rs for rev in ("base", "head"))
                   for c in chain.CLASSES}
        per_fixture[f] = {"valid_blocks": len(rs), "full_chain_blocks": k, "wilson95": wilson(k, len(rs)),
                          "revision_classes": classes}
    k_all = sum(r["full_chain"] for r in rows)
    thin = {f: v["valid_blocks"] for f, v in per_fixture.items()
            if v["valid_blocks"] < (1 if pilot else MIN_VALID_PER_FIXTURE)}
    status = "INCONCLUSIVE_INFRA" if thin else ("HARNESS_INVALID" if not harness_ok else "REPORTED")
    return {"protocol": RP.PROTOCOL, "pilot": pilot, "status": status,
            "overall": {"valid_blocks": len(rows), "full_chain_blocks": k_all,
                        "wilson95": wilson(k_all, len(rows))},
            "per_fixture": per_fixture, "harness": harness, "harness_ok": harness_ok,
            "invalid_blocks": invalid, "blocks": rows}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = score(args.pilot)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "overall", "per_fixture", "harness_ok",
                                             "problems") if k in result}, indent=1))


if __name__ == "__main__":
    main()
