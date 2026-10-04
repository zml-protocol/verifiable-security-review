"""Check the RD boundary cases (PREREGISTRATION.md §15.1, §15.4).

    uv run python experiments/rd/boundary/check.py

Every anchor resolves in its revision (the shared hop anchor rule); every relation is in the RD
vocabulary of its language; every requirement item is well formed (per-revision present/absent
slots, kind-specific payloads); every case has the author's label naming a defined rule; and each
relation, role and qualifier kind has at least one positive and one negative case. Reads the
labels only to check them; the adjudicator-facing files carry none.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "hop_bridge"))

import bridge  # frozen §14: the RD relation vocabulary is P-Hybrid-1's plus the bridge relations

from spike import hops as hoplib

DEFS = yaml.safe_load((ROOT / "experiments" / "rd" / "definitions.yaml").read_text())
REVISIONS = ("vuln", "fixed")
KINDS = {
    "guard": ({"subject", "predicate"}, {"expected": {"must_hold", "must_not_hold"}}),
    "transform": ({"subject", "transform"}, {"expected": {"must_be_present", "must_be_absent"}}),
    "config": ({"subject", "config"}, {"expected_condition": None}),
    "dispatch_target": ({"call", "target"}, {}),
}
OPS = {"equals", "not_equals", "set", "unset"}


def load(name: str) -> dict:
    return yaml.safe_load((HERE / name).read_text())


def rule_ids() -> list[str]:
    ids = [r["id"] for r in DEFS["common"]]
    for rel in DEFS["relations"].values():
        ids += [r["id"] for r in rel.get("rules", [])]
    req = DEFS["requirements"]
    for part in ("entry", "behavior", "absent_context"):
        ids += [r["id"] for r in req[part].get("rules", [])]
    ids += [r["id"] for r in req["state"]]
    ids += [r["id"] for r in DEFS["qualifiers"]["general"]]
    for kind in KINDS:
        ids += [r["id"] for r in DEFS["qualifiers"][kind].get("rules", [])]
    return ids


def anchor_problem(fixture: dict, rev: str, anchor: dict) -> str | None:
    text = bridge.verify.source(fixture, rev, anchor["file"])
    if text is None:
        return f"{anchor['file']} missing at {rev}"
    try:
        hoplib.locate(text, anchor, fixture["language"] == "go")
    except hoplib.HopError as e:
        return str(e)
    return None


def check_relations(cases: dict, labels: dict, defined: set[str]) -> list[str]:
    problems, seen = [], Counter()
    for hop in cases["hops"]:
        hid = hop["id"]
        fixture = cases["fixtures"][hop["fixture"]]
        if hop["relation"] not in bridge.relations(fixture["language"]):
            problems.append(f"{hid}: {hop['relation']} is not an RD relation for {fixture['language']}")
        for side in ("from", "to"):
            if p := anchor_problem(fixture, hop["revision"], hop[side]):
                problems.append(f"{hid} {side}: {p}")
        lab = labels.get(hid)
        if lab is None or not isinstance(lab.get("label"), bool):
            problems.append(f"{hid}: no boolean label")
            continue
        if lab.get("rule") not in defined:
            problems.append(f"{hid}: undefined rule {lab.get('rule')}")
        if lab.get("tier") not in ("core", "boundary"):
            problems.append(f"{hid}: tier must be core or boundary")
        seen[(fixture["language"], hop["relation"], lab["label"])] += 1
        seen[(fixture["language"], hop["relation"], lab.get("tier"))] += 1
    for lang in ("go", "python"):
        for rel in bridge.relations(lang):
            for value in (True, False, "core"):
                if not seen[(lang, rel, value)]:
                    problems.append(f"no {value} case for {lang}/{rel}")
    if extra := set(labels) - {h["id"] for h in cases["hops"]}:
        problems.append(f"labels for unknown cases: {sorted(extra)}")
    return problems


def slot_problems(iid: str, name: str, slot: dict, fixture: dict) -> list[str]:
    problems = []
    if set(slot) != set(REVISIONS):
        return [f"{iid} {name}: needs exactly {REVISIONS}"]
    for rev in REVISIONS:
        real = slot[rev]
        key = {"present": "anchor", "absent": "context"}.get(real.get("state"))
        if key is None or set(real) != {"state", key}:
            problems.append(f"{iid} {name} {rev}: present needs an anchor, absent a context")
            continue
        if p := anchor_problem(fixture, rev, real[key]):
            problems.append(f"{iid} {name} {rev}: {p}")
    if not any(slot[rev].get("state") == "present" for rev in REVISIONS):
        problems.append(f"{iid} {name}: absent at both revisions")
    return problems


def check_requirements(cases: dict, labels: dict, defined: set[str]) -> list[str]:
    problems, seen = [], Counter()
    for sid, sc in cases["scenarios"].items():
        if not str(sc.get("domain") or "").strip():
            problems.append(f"{sid}: the scenario must state what the attacker controls (definitions v2)")
    for it in cases["items"]:
        iid = it["id"]
        sc = cases["scenarios"][it["scenario"]]
        fixture = cases["fixtures"][sc["repo_fixture"]]
        role = it["role"]
        if role == "qualifier":
            kind = it.get("kind")
            if kind not in KINDS:
                problems.append(f"{iid}: kind {kind} not in the closed set")
                continue
            fields, semantic = KINDS[kind]
            if set(it["slots"]) != fields:
                problems.append(f"{iid}: {kind} needs slots {sorted(fields)}")
            got = it.get("semantic") or {}
            if set(got) != set(semantic):
                problems.append(f"{iid}: {kind} needs semantic fields {sorted(semantic)}")
            for field, allowed in semantic.items():
                if allowed and got.get(field) not in allowed:
                    problems.append(f"{iid}: {field}={got.get(field)!r}")
            if kind == "config":
                cond = got.get("expected_condition") or {}
                if cond.get("op") not in OPS or (("value" in cond) != (cond.get("op") in ("equals", "not_equals"))):
                    problems.append(f"{iid}: bad expected_condition {cond}")
            tag = kind
        elif role in ("entry", "behavior"):
            if set(it["slots"]) != {role} or "kind" in it or "semantic" in it:
                problems.append(f"{iid}: a {role} item has exactly one slot, {role}")
            tag = role
        else:
            problems.append(f"{iid}: role {role}")
            continue
        for name, slot in it["slots"].items():
            problems += slot_problems(iid, name, slot, fixture)
        lab = labels.get(iid)
        if lab is None or lab.get("label") not in ("REQUIRED", "NOT_REQUIRED"):
            problems.append(f"{iid}: no REQUIRED/NOT_REQUIRED label")
            continue
        if lab.get("rule") not in defined:
            problems.append(f"{iid}: undefined rule {lab.get('rule')}")
        if lab.get("tier") not in ("core", "boundary"):
            problems.append(f"{iid}: tier must be core or boundary")
        seen[(tag, lab["label"])] += 1
        seen[(tag, lab.get("tier"))] += 1
    for tag in ("entry", "behavior", *KINDS):
        for value in ("REQUIRED", "NOT_REQUIRED", "core"):
            if not seen[(tag, value)]:
                problems.append(f"no {value} case for {tag}")
    if extra := set(labels) - {it["id"] for it in cases["items"]}:
        problems.append(f"labels for unknown items: {sorted(extra)}")
    return problems


def leaks(*docs: dict) -> list[str]:
    """Adjudicator-facing files carry no label, rule or reason."""
    out = []

    def walk(x, path):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("label", "rule", "reason", "expected_label", "name", "tier"):
                    out.append(f"{path}.{k}")
                walk(v, f"{path}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]")
    for d in docs:
        walk(d, d.get("set", "?"))
    return out


def problems() -> list[str]:
    ids = rule_ids()
    out = [f"duplicate rule id {r}" for r, n in Counter(ids).items() if n > 1]
    defined = set(ids)
    rel, req = load("relation_cases.yaml"), load("requirement_cases.yaml")
    out += check_relations(rel, load("relation_labels.yaml")["labels"], defined)
    out += check_requirements(req, load("requirement_labels.yaml")["labels"], defined)
    out += [f"label field in an adjudicator-facing file: {p}" for p in leaks(rel, req)]
    out += [f"id {h['id']} is not opaque" for h in rel["hops"] if not re.fullmatch(r"r\d{2}", h["id"])]
    out += [f"id {it['id']} is not opaque" for it in req["items"] if not re.fullmatch(r"q\d{2}", it["id"])]
    return out


def main() -> None:
    found = problems()
    for p in found:
        print(p)
    rel, req = load("relation_cases.yaml"), load("requirement_cases.yaml")
    print(f"{len(rel['hops'])} relation cases, {len(req['items'])} requirement items, "
          f"{len(set(rule_ids()))} rules, {len(found)} problems")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
