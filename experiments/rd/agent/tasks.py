"""Load the frozen RD task manifest without exposing author-side fields to the agent."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TRUTH = ROOT / "experiments" / "rd" / "truth"
if str(TRUTH) not in sys.path:
    sys.path.insert(0, str(TRUTH))

import revision_map  # noqa: E402

MANIFEST = HERE / "manifest.yaml"
ORDER = HERE / "order.txt"


class TaskError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest() -> dict:
    doc = yaml.safe_load(MANIFEST.read_text())
    if doc.get("schema") != "rd-agent-tasks/v1" or doc.get("protocol") != "rd-v2":
        raise TaskError("unexpected task manifest schema/protocol")
    return doc


def order() -> list[str]:
    ids = [line.split("#", 1)[0].strip() for line in ORDER.read_text().splitlines()]
    ids = [x for x in ids if x]
    known = set(manifest()["tasks"])
    if len(ids) != len(set(ids)) or set(ids) != known:
        raise TaskError("order.txt must contain every task exactly once")
    return ids


def task(task_id: str) -> dict:
    public = manifest()["tasks"].get(task_id)
    if public is None:
        raise TaskError(f"unknown task {task_id!r}")
    fixture = public["fixture"]
    facts_path = ROOT / "runs" / "rd" / "precheck" / fixture / "facts.json"
    truth_path = TRUTH / "fixtures" / fixture / "requirement-truth.yaml"
    facts = json.loads(facts_path.read_text())
    truth = yaml.safe_load(truth_path.read_text())
    canonical = {role: row["commit"] for role, row in truth["truth_meta"]["canonical_revisions"].items()}
    mapping = revision_map.seed_revision_map(fixture)
    revisions = {outward: canonical[role] for outward, role in mapping.items()}
    if canonical != {"vuln": facts["parent"], "fixed": facts["fix_commit"]}:
        raise TaskError(f"truth/facts commit mismatch for {fixture}")
    repo = ROOT / "runs" / "rd" / "precheck" / fixture / "trees" / "fix"
    return {
        "task_id": task_id,
        "fixture": fixture,
        "language": public["language"],
        "claim": {k: public[k] for k in ("package", "cwe", "cwe_name")},
        "repo": str(repo),
        "revisions": revisions,
        "outward_mapping": mapping,
        "role": public["role"],
        "expected_attribution": public["expected_attribution"],
        "truth_path": str(truth_path),
    }


def agent_view(t: dict) -> dict:
    """The only task fields allowed through get_task."""
    return {"task_id": t["task_id"], "language": t["language"], "claim": t["claim"]}
