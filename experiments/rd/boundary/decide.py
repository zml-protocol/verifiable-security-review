"""Mechanical comparison for the RD decidability test (PREREGISTRATION.md §15.1, steps 2 and 5).

    uv run python experiments/rd/boundary/decide.py --round 1

Reads the author's labels and the two adjudicators' label files of a round
(results/rd-boundary-r<N>-judge-{a,b}.yaml), checks them against the round's manifest, and
compares author, A and B case by case. Written and committed before any adjudicator labels.

Groups: each relation per language (go/def_use and python/def_use apart, as the verifiers are),
entry, behavior, and each qualifier kind. A case agrees only when all three give the same label
(an adjudicator's INDETERMINATE never agrees). Per group:
- AGREED: every case agrees.
- otherwise DISPUTED. The author may revise the group's definition text once; two new sessions
  then relabel all of the group's cases (round 2). Without a revision, or after round 2, the
  outcome is final:
  - a dispute on a core case: a relation or qualifier kind leaves the RD vocabulary
    (EXIT_VOCABULARY); entry or behavior cannot leave it, so the case goes back to Codex (ESCALATE);
  - disputes on boundary cases only: those cases' rules become INDETERMINATE regions
    (INDETERMINATE_BOUNDARY); the group stays.
Label files may write TRUE/FALSE and the date unquoted: YAML booleans and dates are normalized
here, by design, before any file is read.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESULTS = ROOT / "results"
sys.path.insert(0, str(HERE))

import check as C
from sheet import ATTESTATION, RELATION_LABELS, REQUIREMENT_LABELS

JUDGES = ("a", "b")
ENTRY_BEHAVIOR = ("entry", "behavior")


def normalize(value) -> str | None:
    if value is True:
        return "TRUE"
    if value is False:
        return "FALSE"
    return value if isinstance(value, str) else None


def load_judge(path: Path, manifest: dict) -> tuple[dict | None, list[str]]:
    """{"reviewer", "relations": id -> label, "requirements": id -> label}, or None with problems."""
    if not path.exists():
        return None, [f"{path.name}: missing"]
    doc = yaml.safe_load(path.read_text())
    problems = []
    rev = doc.get("reviewer") if isinstance(doc, dict) else None
    if not isinstance(rev, dict) or rev.get("type") not in ("model", "human") or not str(rev.get("name") or "").strip():
        problems.append(f"{path.name}: reviewer type and name required")
    else:
        if isinstance(rev.get("date"), datetime.date):
            rev["date"] = rev["date"].isoformat()
        attest = rev.get("attestation")
        if not isinstance(attest, dict) or any(attest.get(k) is not v for k, v in ATTESTATION.items()):
            problems.append(f"{path.name}: attestation must be {ATTESTATION}")
    out = {"reviewer": rev, "relations": {}, "requirements": {}}
    for part, allowed in (("relations", RELATION_LABELS), ("requirements", REQUIREMENT_LABELS)):
        raw = (doc or {}).get(part) or {}
        if set(raw) != set(manifest[part]):
            problems.append(f"{path.name}: {part} ids differ from the manifest")
        for cid, value in raw.items():
            label = normalize(value.get("label") if isinstance(value, dict) else value)
            if label not in allowed:
                problems.append(f"{path.name}: {cid} label {label!r}")
            out[part][cid] = label
    return (None if problems else out), problems


def groups(rel_cases: dict, req_cases: dict) -> dict[str, str]:
    """case id -> group."""
    g = {h["id"]: f"{rel_cases['fixtures'][h['fixture']]['language']}/{h['relation']}" for h in rel_cases["hops"]}
    g |= {it["id"]: it["role"] if it["role"] in ENTRY_BEHAVIOR else it["kind"] for it in req_cases["items"]}
    return g


def outcome(group: str, disputed: list[dict]) -> str:
    if not disputed:
        return "ADMISSIBLE"
    if any(d["tier"] == "core" for d in disputed):
        return "ESCALATE" if group in ENTRY_BEHAVIOR else "EXIT_VOCABULARY"
    return "INDETERMINATE_BOUNDARY"


def compare(author: dict, judges: dict, group_of: dict) -> dict:
    """author: id -> {label, rule, tier}; judges: name -> id -> label."""
    per_group: dict[str, dict] = {}
    for cid, a in author.items():
        g = per_group.setdefault(group_of[cid], {"cases": 0, "disputed": []})
        g["cases"] += 1
        votes = {"author": a["label"], **{j: judges[j][cid] for j in judges}}
        if len(set(votes.values())) != 1 or "INDETERMINATE" in votes.values():
            g["disputed"].append({"id": cid, "rule": a["rule"], "tier": a["tier"], **votes})
    for name, g in per_group.items():
        g["status"] = "AGREED" if not g["disputed"] else "DISPUTED"
        g["outcome_without_revision"] = outcome(name, g["disputed"])
        g["indeterminate_rules"] = sorted({d["rule"] for d in g["disputed"]}) \
            if g["outcome_without_revision"] == "INDETERMINATE_BOUNDARY" else []
    return dict(sorted(per_group.items()))


def author_labels() -> dict:
    rel = C.load("relation_labels.yaml")["labels"]
    req = C.load("requirement_labels.yaml")["labels"]
    out = {cid: {"label": "TRUE" if v["label"] else "FALSE", "rule": v["rule"], "tier": v["tier"]}
           for cid, v in rel.items()}
    out |= {cid: {"label": v["label"], "rule": v["rule"], "tier": v["tier"]} for cid, v in req.items()}
    return out


def run(n: int) -> dict:
    manifest = json.loads((RESULTS / f"rd-boundary-r{n}-manifest.json").read_text())
    defs = ROOT / manifest["definitions"]["file"]
    problems = []
    if hashlib.sha256(defs.read_bytes()).hexdigest() != manifest["definitions"]["sha256"]:
        problems.append("definitions changed since the sheet was written")
    for name, h in manifest["cases"].items():
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != h:
            problems.append(f"{name} changed since the sheet was written")
    judges = {}
    for j in JUDGES:
        doc, p = load_judge(RESULTS / f"rd-boundary-r{n}-judge-{j}.yaml", manifest)
        problems += p
        if doc:
            judges[j] = doc
    if problems:
        return {"round": n, "status": "NOT_SCORABLE", "problems": problems}
    rel_cases, req_cases = C.load("relation_cases.yaml"), C.load("requirement_cases.yaml")
    ids = set(manifest["relations"]) | set(manifest["requirements"])
    author = {cid: v for cid, v in author_labels().items() if cid in ids}
    labels = {j: judges[j]["relations"] | judges[j]["requirements"] for j in JUDGES}
    result = compare(author, labels, groups(rel_cases, req_cases))
    pairs = {"author~a": 0, "author~b": 0, "a~b": 0}
    for cid in author:
        pairs["author~a"] += author[cid]["label"] == labels["a"][cid]
        pairs["author~b"] += author[cid]["label"] == labels["b"][cid]
        pairs["a~b"] += labels["a"][cid] == labels["b"][cid]
    return {"round": n, "status": "SCORED", "reviewers": {j: judges[j]["reviewer"] for j in JUDGES},
            "cases": len(author), "pairwise_agreement": pairs, "groups": result}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--round", type=int, required=True)
    n = ap.parse_args().round
    result = run(n)
    (RESULTS / f"rd-boundary-r{n}-decision.json").write_text(json.dumps(result, indent=2) + "\n")
    if result["status"] != "SCORED":
        print("\n".join(result["problems"]))
        sys.exit(1)
    for g, v in result["groups"].items():
        print(f"{g:28} {v['status']:9} {len(v['disputed'])}/{v['cases']} disputed -> {v['outcome_without_revision']}")


if __name__ == "__main__":
    main()
