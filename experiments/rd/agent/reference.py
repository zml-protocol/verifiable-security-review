"""Verify the author-side §15.3 reference evidence before any measured agent run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TRUTH = ROOT / "experiments" / "rd" / "truth"
if str(TRUTH) not in sys.path:
    sys.path.insert(0, str(TRUTH))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import revision_map  # noqa: E402

import graph  # noqa: E402
import schema  # noqa: E402
import tasks  # noqa: E402


def _truth_requirements(fixture: str) -> dict:
    raw = yaml.safe_load((TRUTH / "fixtures" / fixture / "requirement-truth.yaml").read_text())
    mapped = revision_map.map_doc(raw, fixture)
    found = {item["kind"]: item[item["kind"]] for item in mapped["items"]
             if item["kind"] in ("entry", "behavior")}
    found["required_qualifiers"] = [
        {k: v for k, v in item.items() if k not in ("id", "author_expected")}
        for item in mapped["items"] if item["kind"] not in ("entry", "behavior")
    ]
    return found


def _real_task(fixture: str) -> dict:
    matches = [tasks.task(tid) for tid, row in tasks.manifest()["tasks"].items()
               if row["fixture"] == fixture and row["role"] == "real"]
    if len(matches) != 1:
        raise RuntimeError(f"expected one real task for {fixture}; got {len(matches)}")
    return matches[0]


def verify_fixture(fixture: str, *, write: bool = True) -> dict:
    t = _real_task(fixture)
    path = TRUTH / "fixtures" / fixture / "reference-evidence.yaml"
    author = yaml.safe_load(path.read_text())
    if author.get("schema") != "rd-reference-evidence/v1" or author.get("fixture") != fixture:
        raise RuntimeError(f"bad reference evidence header: {path}")
    if set(author.get("revisions") or {}) != {"vuln", "fixed"}:
        raise RuntimeError(f"reference evidence must cover canonical vuln/fixed: {path}")
    mapping = revision_map.canonical_to_outward(fixture)
    requirements = _truth_requirements(fixture)
    analyses = graph.load_analysis({rev: str(ROOT / "runs/rd/agent/analysis" / t["task_id"] / rev /
                                                    "analysis.json.gz")
                                    for rev in schema.REVISIONS})
    scorer = graph.GraphScorer(language=t["language"], repo=t["repo"],
                               revisions=t["revisions"], analysis=analyses)
    checked, problems = [], []
    for canonical in ("vuln", "fixed"):
        outward = mapping[canonical]
        row = author["revisions"][canonical]
        required = requirements["entry"][outward]["state"] == "present" and \
            requirements["behavior"][outward]["state"] == "present"
        if row.get("chain_required") is not required:
            problems.append(f"{canonical}: chain_required={row.get('chain_required')} but truth says {required}")
        hops = row.get("hops") or []
        if not required and hops:
            problems.append(f"{canonical}: a non-required revision must have no reference hops")
        if required and not isinstance(row.get("semantic_chain_complete"), bool):
            problems.append(f"{canonical}: required chain needs semantic_chain_complete boolean")
        states = []
        for i, raw in enumerate(hops, 1):
            h = {"revision": outward, **raw}
            try:
                clean = schema.hop(h, set(scorer.relations))
                state, _ = scorer.resolve_hop(clean)
                states.append({"hop": clean, "state": state})
            except Exception as e:
                problems.append(f"{canonical} hop {i}: {e}")
        checked.append({"canonical_revision": canonical, "outward_revision": outward,
                        "chain_required": required,
                        "semantic_chain_complete": row.get("semantic_chain_complete") if required else None,
                        "reason": row.get("reason"), "hops": states})
    if problems:
        raise RuntimeError("; ".join(problems))
    b = {"hops": [{"hop": item["hop"], "state": item["state"]}
                   for row in checked for item in row["hops"]]}
    classification = scorer.classify({"requirements": requirements}, b)
    required_rows = [row for row in checked if row["chain_required"]]
    if any(not row["semantic_chain_complete"] for row in required_rows):
        disposition = "REFERENCE_UNREALIZABLE"
    elif classification["full_chain"]:
        disposition = "FULLY_VERIFIED_REFERENCE"
    else:
        states = [hop["state"] for row in required_rows for hop in row["hops"]]
        if not states or all(state == "VERIFIED" for state in states):
            raise RuntimeError("reference has no provider gap but does not form a full chain; author reference is incomplete")
        disposition = "PROVIDER_BLIND"
    result = {"schema": "rd-reference-result/v1", "fixture": fixture,
              "task_id": t["task_id"], "disposition": disposition,
              "revisions": checked, "classification": classification}
    if write:
        out = path.with_name("reference-result.json")
        out.write_text(json.dumps(result, indent=2) + "\n")
        print(f"{fixture}: {disposition} -> {out.relative_to(ROOT)}")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fixture", nargs="*")
    args = ap.parse_args()
    fixtures = args.fixture or [tasks.task(tid)["fixture"] for tid in tasks.order()
                                if tasks.task(tid)["role"] == "real"]
    for fixture in dict.fromkeys(fixtures):
        verify_fixture(fixture)


if __name__ == "__main__":
    main()
