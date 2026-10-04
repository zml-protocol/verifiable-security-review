"""Audit RD v3 author reference evidence against the exact frozen provider.

The audit is task-manifest driven so it can run before a formal model call without
depending on the v2 task queue.  It never replaces a fixture and never edits truth.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[3]
TRUTH_TOOLS = ROOT / "experiments" / "rd" / "truth"
for directory in (PARENT, TRUTH_TOOLS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import graph  # noqa: E402
import schema  # noqa: E402

FULL = "REFERENCE_FULLY_VERIFIED"
BLIND = "PROVIDER_BLIND"
UNREALIZABLE = "REFERENCE_UNREALIZABLE"
INVALID = "REFERENCE_INVALID"


class ReferenceInvalid(RuntimeError):
    pass


def _load(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def truth_requirements(task: dict) -> dict:
    raw = _load(task["truth_path"])
    c2o = task.get("canonical_to_outward")
    if not isinstance(c2o, dict) or set(c2o) != {"vuln", "fixed"} \
            or set(c2o.values()) != set(schema.REVISIONS):
        raise ReferenceInvalid("task has no bijective canonical-to-outward mapping")
    mapped = copy.deepcopy(raw)
    for item in mapped.get("items") or []:
        if not isinstance(item, dict):
            continue
        for value in item.values():
            if not isinstance(value, dict):
                continue
            if set(value) & set(schema.REVISIONS):
                raise ReferenceInvalid("truth already uses outward revision keys")
            if set(value) & {"vuln", "fixed"}:
                if set(value) != {"vuln", "fixed"}:
                    raise ReferenceInvalid("canonical truth slot must contain vuln and fixed")
                relabeled = {c2o[canonical]: copy.deepcopy(realization)
                             for canonical, realization in value.items()}
                value.clear()
                value.update(relabeled)
    slots = {item["kind"]: item[item["kind"]] for item in mapped["items"]
             if item["kind"] in ("entry", "behavior")}
    if set(slots) != {"entry", "behavior"}:
        raise ReferenceInvalid("truth must contain exactly one entry and one behavior")
    slots["required_qualifiers"] = [
        {key: copy.deepcopy(value) for key, value in item.items()
         if key not in ("id", "author_expected")}
        for item in mapped["items"] if item["kind"] not in ("entry", "behavior")
    ]
    return slots


def _required(requirements: dict, revision: str) -> bool:
    return (requirements["entry"][revision]["state"] == "present" and
            requirements["behavior"][revision]["state"] == "present")


def _qualifier_present(qualifier: dict, revision: str) -> bool:
    names = {"guard": ("subject", "predicate"), "config": ("subject", "config"),
             "dispatch_target": ("call", "target")}[qualifier["kind"]]
    return any(qualifier[name][revision]["state"] == "present" for name in names)


def audit(task: dict, evidence_path: str | Path) -> dict:
    if task.get("task_kind") != "real":
        raise ReferenceInvalid("reference audit applies only to real tasks")
    author = _load(evidence_path)
    if author.get("schema") != "rd-v3-reference-evidence/v1":
        raise ReferenceInvalid("bad v3 reference-evidence schema")
    if author.get("fixture") != task.get("fixture") or author.get("task_id") != task.get("task_id"):
        raise ReferenceInvalid("reference evidence does not identify the task")
    revisions = author.get("revisions")
    if not isinstance(revisions, dict) or set(revisions) != {"vuln", "fixed"}:
        raise ReferenceInvalid("reference evidence must cover canonical vuln and fixed")

    mapping = task.get("canonical_to_outward")
    if not isinstance(mapping, dict) or set(mapping) != {"vuln", "fixed"} \
            or set(mapping.values()) != set(schema.REVISIONS):
        raise ReferenceInvalid("task has no bijective canonical-to-outward mapping")
    requirements = truth_requirements(task)
    analyses = graph.load_analysis(task["analysis"])
    scorer = graph.GraphScorer(language=task["language"], repo=task["repo"],
                               revisions=task["revisions"], analysis=analyses)

    checked, problems = [], []
    for canonical in ("vuln", "fixed"):
        outward = mapping[canonical]
        row = revisions[canonical]
        if not isinstance(row, dict):
            problems.append(f"{canonical}: evidence row must be an object")
            continue
        needed = _required(requirements, outward)
        if row.get("chain_required") is not needed:
            problems.append(f"{canonical}: chain_required disagrees with truth")
        hops = row.get("hops")
        if not isinstance(hops, list):
            problems.append(f"{canonical}: hops must be a list")
            hops = []
        semantic = row.get("semantic_chain_complete") if needed else None
        if needed and not isinstance(semantic, bool):
            problems.append(f"{canonical}: required chain needs semantic_chain_complete boolean")
        if not needed and hops:
            problems.append(f"{canonical}: non-required revision must not contain hops")
        states = []
        for number, raw in enumerate(hops, 1):
            try:
                clean = schema.hop({"revision": outward, **raw}, set(scorer.relations))
                state, _ = scorer.resolve_hop(clean)
                states.append({"hop": clean, "state": state})
            except Exception as exc:
                problems.append(f"{canonical} hop {number}: {exc}")
        checked.append({"canonical_revision": canonical, "outward_revision": outward,
                        "chain_required": needed, "semantic_chain_complete": semantic,
                        "reason": row.get("reason"), "hops": states})
    if problems:
        raise ReferenceInvalid("; ".join(problems))

    b = {"hops": [{"hop": item["hop"], "state": item["state"]}
                   for row in checked for item in row["hops"]]}
    classification = scorer.classify({"requirements": requirements}, b)
    obligations = []
    for row in checked:
        if not row["chain_required"]:
            continue
        outward = row["outward_revision"]
        chain_requirements = {**copy.deepcopy(requirements), "required_qualifiers": []}
        revision_class = scorer.classify(
            {"requirements": chain_requirements}, b)["revisions"][outward]["class"]
        if not row["semantic_chain_complete"]:
            disposition = UNREALIZABLE
        elif revision_class == "FULL_CHAIN":
            disposition = FULL
        elif any(hop["state"] != "VERIFIED" for hop in row["hops"]):
            disposition = BLIND
        else:
            raise ReferenceInvalid(
                f"{row['canonical_revision']}: verified evidence does not form the declared semantic chain")
        obligations.append({"id": f"chain:{row['canonical_revision']}", "kind": "chain",
                            "canonical_revision": row["canonical_revision"],
                            "outward_revision": outward, "disposition": disposition,
                            "graph_class": revision_class})

        for index, qualifier in enumerate(requirements["required_qualifiers"], 1):
            if not _qualifier_present(qualifier, outward):
                continue
            one = {**copy.deepcopy(requirements),
                   "required_qualifiers": [copy.deepcopy(qualifier)]}
            one_class = scorer.classify({"requirements": one}, b)["revisions"][outward]["class"]
            if not row["semantic_chain_complete"]:
                q_disposition = UNREALIZABLE
            elif one_class == "FULL_CHAIN":
                q_disposition = FULL
            elif any(hop["state"] != "VERIFIED" for hop in row["hops"]):
                q_disposition = BLIND
            else:
                raise ReferenceInvalid(
                    f"{row['canonical_revision']} qualifier {index}: verified evidence has no attachment")
            obligations.append({"id": f"qualifier:{index}:{row['canonical_revision']}",
                                "kind": qualifier["kind"],
                                "canonical_revision": row["canonical_revision"],
                                "outward_revision": outward, "disposition": q_disposition,
                                "graph_class": one_class})

    dispositions = {row["disposition"] for row in obligations}
    if not obligations:
        task_disposition = FULL
    elif UNREALIZABLE in dispositions:
        task_disposition = UNREALIZABLE
    elif BLIND in dispositions:
        task_disposition = BLIND
    elif dispositions == {FULL}:
        task_disposition = FULL
    else:
        raise ReferenceInvalid(f"unrecognized obligation dispositions: {sorted(dispositions)}")
    return {"schema": "rd-v3-reference-result/v1", "task_id": task["task_id"],
            "fixture": task["fixture"], "disposition": task_disposition,
            "obligations": obligations, "revisions": checked,
            "classification": classification}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", type=Path, help="one real-task JSON object")
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    task = json.loads(args.task.read_text())
    try:
        result = audit(task, args.evidence)
    except ReferenceInvalid as exc:
        result = {"schema": "rd-v3-reference-result/v1", "task_id": task.get("task_id"),
                  "fixture": task.get("fixture"), "disposition": INVALID,
                  "problems": [str(exc)]}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n")
        raise SystemExit(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{task['task_id']}: {result['disposition']}")


if __name__ == "__main__":
    main()
