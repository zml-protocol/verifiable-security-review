"""Score RD v2 without reading measured assistant prose.

Only sealed artifacts, machine transcripts, CLI metadata, frozen truth and reference
results are read.  Write the result and commit it before human transcript inspection.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TRUTH = ROOT / "experiments" / "rd" / "truth"
# Keep this directory first: agent_verify also has a run.py, and importing that
# runner would silently bind the scorer to a different experiment.
for directory in (TRUTH, ROOT / "experiments" / "agent_verify"):
    if str(directory) not in sys.path:
        sys.path.append(str(directory))
if str(HERE) in sys.path:
    sys.path.remove(str(HERE))
sys.path.insert(0, str(HERE))

from validity import agent_events  # noqa: E402

import agreement  # noqa: E402
import resolver  # noqa: E402
import revision_map  # noqa: E402

import graph  # noqa: E402
import schema  # noqa: E402
import tasks  # noqa: E402
from source import SourceSurface  # noqa: E402


def _local_module(name: str, filename: str):
    """Load a protocol module without trusting collision-prone generic names."""
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local module {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


freeze = _local_module("rd_agent_v2_freeze_for_score", "freeze.py")
runner = _local_module("rd_agent_v2_runner", "run.py")


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def metric(k: int, n: int) -> dict:
    return {"numerator": k, "denominator": n, "rate": round(k / n, 4) if n else None,
            "wilson95": wilson(k, n)}


def _freeze(value):
    if isinstance(value, list):
        return tuple(_freeze(x) for x in value)
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    return value


def _identity(anchor: dict):
    return _freeze(anchor.get("node_identity")) if isinstance(anchor, dict) else None


def _agent_items(a: dict) -> list[dict]:
    req = a["requirements"]
    items = [{"id": "agent-entry", "kind": "entry", "entry": req["entry"]},
             {"id": "agent-behavior", "kind": "behavior", "behavior": req["behavior"]}]
    for i, q in enumerate(req.get("required_qualifiers") or [], 1):
        if q["kind"] != "UNSUPPORTED_REQUIREMENT_TYPE":
            items.append({"id": f"agent-q{i}", **q})
    return items


def _resolved_docs(t: dict, a: dict) -> tuple[list[dict], list[dict]]:
    source = SourceSurface(t["repo"], t["revisions"])
    provider = lambda revision, file: source.text(revision, file)
    truth = yaml.safe_load(Path(t["truth_path"]).read_text())
    truth = revision_map.map_doc(truth, t["fixture"])
    truth = resolver.resolve_doc({"items": truth["items"]}, language=t["language"],
                                 source_provider=provider)
    agent = resolver.resolve_doc({"items": _agent_items(a)}, language=t["language"],
                                 source_provider=provider)
    return truth["items"], agent["items"]


def _item_matches(truth_items: list[dict], agent_items: list[dict]) -> dict:
    truths = [x for x in truth_items if x["kind"] in ("entry", "behavior", "guard", "config",
                                                        "dispatch_target")]
    used, pairs = set(), []
    for truth in truths:
        ti = agreement.item_identity(truth, _identity)
        match = next((i for i, agent in enumerate(agent_items)
                      if i not in used and agreement.item_identity(agent, _identity) == ti), None)
        if match is not None:
            used.add(match)
            pairs.append((truth, agent_items[match]))
    result = {}
    for kind in ("entry", "behavior", "qualifier"):
        tk = [x for x in truths if (x["kind"] if x["kind"] in ("entry", "behavior") else "qualifier") == kind]
        ak = [x for x in agent_items if (x["kind"] if x["kind"] in ("entry", "behavior") else "qualifier") == kind]
        matched = sum((t, a) in pairs for t in tk for a in ak)
        result[kind] = {"truth": len(tk), "proposed": len(ak), "matched": matched}
    matched_truth = {t["id"] for t, _ in pairs}
    matched_agent = {a["id"] for _, a in pairs}
    extra_qualifiers = [a["id"] for a in agent_items
                        if a["kind"] not in ("entry", "behavior") and a["id"] not in matched_agent]
    required = {t["id"] for t in truths}
    partial = []
    for truth in truths:
        if truth["id"] in matched_truth:
            continue
        for agent in agent_items:
            if agent["kind"] != truth["kind"]:
                continue
            revisions = []
            for revision in schema.REVISIONS:
                def one(item: dict):
                    fields = []
                    for key, value in sorted(item.items()):
                        if key in agreement.UNSCORED:
                            continue
                        if isinstance(value, dict) and revision in value:
                            realization = value[revision]
                            state = realization.get("state")
                            anchor_key = "anchor" if state == "present" else "context"
                            fields.append((key, state, _identity(realization.get(anchor_key))))
                        elif not isinstance(value, dict):
                            fields.append((key, _freeze(value)))
                    return tuple(fields)
                if one(truth) == one(agent):
                    revisions.append(revision)
            if revisions:
                partial.append({"truth": truth["id"], "agent": agent["id"], "revisions": revisions})
    return {"counts": result, "pairs": [{"truth": t["id"], "agent": a["id"]} for t, a in pairs],
            "truth_matching": matched_truth == required and not extra_qualifiers,
            "unmatched_truth": sorted(required - matched_truth), "extra_qualifiers": extra_qualifiers,
            "partial_revision_matches": partial}


def _empty_a(t: dict) -> dict:
    truth = yaml.safe_load(Path(t["truth_path"]).read_text())
    counts = {}
    for kind in ("entry", "behavior", "qualifier"):
        n = sum((item["kind"] if item["kind"] in ("entry", "behavior") else "qualifier") == kind
                for item in truth["items"])
        counts[kind] = {"truth": n, "proposed": 0, "matched": 0}
    return {"counts": counts, "pairs": [], "truth_matching": False,
            "unmatched_truth": [item["id"] for item in truth["items"]],
            "extra_qualifiers": [], "partial_revision_matches": []}


def attribution(conclusion: dict, mapping: dict[str, str]) -> tuple[str, dict]:
    canonical = {role: conclusion[outward] for outward, role in mapping.items()}
    pair = (canonical["vuln"], canonical["fixed"])
    if pair == ("SUPPORTED", "NOT_SUPPORTED"):
        label = "FIX_IMPLICATED"
    elif pair == ("NOT_SUPPORTED", "SUPPORTED"):
        label = "CHANGE_IMPLICATED"
    elif pair == ("SUPPORTED", "SUPPORTED"):
        label = "PRE_EXISTING"
    elif pair == ("NOT_SUPPORTED", "NOT_SUPPORTED"):
        label = "NOT_SUPPORTED"
    else:
        label = "UNDETERMINED"
    return label, canonical


def _foreign_tools(phase_dir: Path) -> list[str]:
    names = set()
    for event in agent_events(phase_dir):
        if event.get("type") != "assistant":
            continue
        for content in (event.get("message") or {}).get("content", []):
            if content.get("type") == "tool_use" and not content.get("name", "").startswith("mcp__secreview__"):
                names.add(content.get("name", ""))
    return sorted(names)


def _attempt(task_id: str) -> Path | None:
    root = runner.RUNS / task_id
    attempts = sorted(root.glob("attempt-*")) if root.exists() else []
    if not attempts:
        return None
    terminal = [p for p in attempts if json.loads((p / "attempt.json").read_text())["status"] != "INFRA_INVALID"]
    return terminal[-1] if terminal else attempts[-1]


def harness_problems(t: dict, attempt: Path) -> list[str]:
    problems = []
    metas = {}
    record_path = attempt / "attempt.json"
    record = json.loads(record_path.read_text()) if record_path.exists() else {"phases": []}
    attempted = {row.get("phase"): row for row in record.get("phases") or []}
    allowed = runner.PHASE_TOOLS
    for phase in ("a", "b", "c"):
        pdir = attempt / f"phase-{phase}"
        meta_path = pdir / "meta.json"
        if not meta_path.exists():
            if phase in attempted and attempted[phase].get("status") != "BUDGET_CENSORED":
                problems.append(f"{phase}: missing execution metadata")
            continue  # agent non-completion can legitimately stop before later phases
        meta = json.loads(meta_path.read_text())
        metas[phase] = meta
        expected = {"a": (3.0, 3.0, 1200), "b": (3.0, 6.0, 1800),
                    "c": (1.0, 7.0, 600)}[phase]
        if (meta.get("model"), meta.get("effort"), meta.get("claude_code_version"),
                meta.get("phase_budget_usd"), meta.get("max_budget_usd"), meta.get("timeout")) != \
                (runner.MODEL, runner.EFFORT, runner.CLI_VERSION, *expected):
            problems.append(f"{phase}: execution config drift")
        env = meta.get("agent_environment") or {}
        cwd = env.get("cwd")
        if not cwd or Path(cwd).resolve().is_relative_to(ROOT):
            problems.append(f"{phase}: cwd not isolated")
        if env.get("model") != runner.MODEL:
            problems.append(f"{phase}: served model drift")
        expected_tools = {f"mcp__secreview__{name}" for name in allowed[phase]}
        if set(env.get("tools") or []) != expected_tools:
            problems.append(f"{phase}: exposed tool surface drift")
        if env.get("memory_files"):
            problems.append(f"{phase}: non-empty auto-memory")
        if _foreign_tools(pdir):
            problems.append(f"{phase}: foreign tools {_foreign_tools(pdir)}")
        transcript = pdir / "transcript.jsonl"
        if transcript.exists():
            for line in transcript.read_text().splitlines():
                event = json.loads(line)
                if event.get("tool") not in allowed[phase]:
                    problems.append(f"{phase}: unexpected server tool {event.get('tool')}")
                text = json.dumps(event)
                if str(ROOT) in text or t["fixture"] in text or any(c in text for c in t["revisions"].values()):
                    problems.append(f"{phase}: context leak in tool ledger")
                if '"internal_error"' in text:
                    problems.append(f"{phase}: internal server error")
    if len(metas) > 1:
        if len({m["agent_environment"].get("cwd") for m in metas.values()}) != 1:
            problems.append("phase cwd changed")
        served = {m["agent_environment"].get("served_session") for m in metas.values()}
        if None in served or len(served) != 1:
            problems.append("phases did not resume one served session")
    return sorted(set(problems))


def score_task(task_id: str) -> tuple[dict, list[str]]:
    t, problems = tasks.task(task_id), []
    attempt = _attempt(task_id)
    if attempt is None:
        row = {"task_id": task_id, "status": "MISSING", "role": t["role"],
               "fixture": t["fixture"], "phases_locked": []}
        if t["role"] == "real":
            row["a"] = _empty_a(t)
            ref = json.loads((Path(t["truth_path"]).parent / "reference-result.json").read_text())
            row["reference_disposition"] = ref["disposition"]
            row["correct_verified_implementation"] = False
            row["failure_category"] = "RUN_MISSING"
        return row, []
    record = json.loads((attempt / "attempt.json").read_text())
    problems += harness_problems(t, attempt)
    artifacts = attempt / "artifacts"
    locked = {}
    for phase in ("a", "b", "c"):
        path = artifacts / f"{phase}.json"
        if path.exists():
            try:
                locked[phase] = json.loads(path.read_text())
                schema.verify_seal(locked[phase])
            except Exception as e:
                problems.append(f"{phase}: bad seal/artifact: {e}")
    row = {"task_id": task_id, "role": t["role"], "fixture": t["fixture"],
           "attempt": attempt.name, "run_status": record["status"],
           "phases_locked": sorted(locked),
           "unsupported_proposals": (sum(q["kind"] == "UNSUPPORTED_REQUIREMENT_TYPE"
                                         for q in locked.get("a", {}).get("requirements", {})
                                         .get("required_qualifiers", [])) if "a" in locked else None)}
    if "a" in locked and t["role"] == "real":
        try:
            truth_items, agent_items = _resolved_docs(t, locked["a"])
            row["a"] = _item_matches(truth_items, agent_items)
        except Exception as e:
            problems.append(f"A scoring failed: {e}")
    elif t["role"] == "real":
        row["a"] = _empty_a(t)
    if "a" in locked and "b" in locked:
        if locked["b"].get("a_seal") != locked["a"].get("seal"):
            problems.append("B does not bind locked A")
        try:
            g = graph.GraphScorer(language=t["language"], repo=t["repo"], revisions=t["revisions"],
                                  analysis=graph.load_analysis(runner.analysis_paths(task_id)))
            row["b"] = g.classify(locked["a"], locked["b"])
            problems += [f"B graph: {m}" for m in row["b"]["harness_mismatches"]]
        except Exception as e:
            problems.append(f"B scoring failed: {e}")
    if "c" in locked:
        if "a" not in locked or "b" not in locked or locked["c"].get("a_seal") != locked["a"].get("seal") \
                or locked["c"].get("b_seal") != locked["b"].get("seal"):
            problems.append("C does not bind locked A/B")
        label, canonical = attribution(locked["c"]["conclusion"], t["outward_mapping"])
        row["c"] = {"canonical_statuses": canonical, "attribution": label,
                    "expected": t["expected_attribution"], "correct": label == t["expected_attribution"]}
    if t["role"] == "real":
        ref = json.loads((Path(t["truth_path"]).parent / "reference-result.json").read_text())
        row["reference_disposition"] = ref["disposition"]
        a_ok = (row.get("a") or {}).get("truth_matching", False)
        b_full = (row.get("b") or {}).get("full_chain", False)
        c_ok = (row.get("c") or {}).get("correct", False)
        row["correct_verified_implementation"] = a_ok and b_full
        if not a_ok:
            row["failure_category"] = "A_WRONG_C_CORRECT" if c_ok else "A_WRONG_B_UNREALIZABLE"
        elif b_full:
            row["failure_category"] = "A_B_C_CORRECT" if c_ok else "A_B_CORRECT_C_WRONG"
        elif ref["disposition"] == "REFERENCE_UNREALIZABLE":
            row["failure_category"] = "REFERENCE_UNREALIZABLE"
        elif ref["disposition"] == "PROVIDER_BLIND":
            row["failure_category"] = "A_CORRECT_PROVIDER_BLIND"
        elif any(x["class"] == "QUALIFIER_GAP" for x in (row.get("b") or {}).get("revisions", {}).values()):
            row["failure_category"] = "A_CORRECT_QUALIFIER_GAP"
        else:
            row["failure_category"] = "A_CORRECT_B_INCOMPLETE"
    return row, problems


def score() -> dict:
    freeze.verify()
    rows, harness = [], {}
    for task_id in tasks.order():
        row, problems = score_task(task_id)
        rows.append(row)
        if problems:
            harness[task_id] = problems
    real = [r for r in rows if r.get("role") == "real"]
    negative = [r for r in rows if r.get("role") == "negative_control"]
    a_metrics = {}
    for kind in ("entry", "behavior", "qualifier"):
        matched = sum((r.get("a") or {}).get("counts", {}).get(kind, {}).get("matched", 0) for r in real)
        truth_n = sum((r.get("a") or {}).get("counts", {}).get(kind, {}).get("truth", 0) for r in real)
        proposed = sum((r.get("a") or {}).get("counts", {}).get(kind, {}).get("proposed", 0) for r in real)
        a_metrics[kind] = {"recall": metric(matched, truth_n), "precision": metric(matched, proposed)}
    c_real_k = sum(bool((r.get("c") or {}).get("correct")) for r in real)
    realizable = [r for r in real if r.get("reference_disposition") != "REFERENCE_UNREALIZABLE"]
    false_supported = sum(status == "SUPPORTED" for r in negative
                          for status in (r.get("c") or {}).get("canonical_statuses", {}).values())
    false_supported_n = 2 * len(negative)
    unfinished = any(r.get("status") == "MISSING" or
                     r.get("run_status") in ("INFRA_INVALID", "BUDGET_CENSORED") for r in rows)
    status = "HARNESS_INVALID" if harness else ("RUN_INCOMPLETE" if unfinished else "REPORTED")
    return {"schema": "rd-score/v1", "protocol": runner.PROTOCOL, "status": status,
            "harness_ok": not harness, "harness_problems": harness,
            "metrics": {"a": a_metrics,
                        "b_full_chain": metric(sum(bool((r.get("b") or {}).get("full_chain")) for r in real), len(real)),
                        "b_correct_verified": metric(sum(bool(r.get("correct_verified_implementation")) for r in real), len(real)),
                        "b_correct_verified_reference_realizable_subset": metric(
                            sum(bool(r.get("correct_verified_implementation")) for r in realizable),
                            len(realizable)),
                        "c_real_attribution_accuracy": metric(c_real_k, len(real)),
                        "negative_control_false_supported_rate": metric(false_supported, false_supported_n),
                        "negative_control_missing_conclusions": sum("c" not in r for r in negative),
                        "unsupported_proposal_burden": sum((r.get("unsupported_proposals") or 0) for r in rows)},
            "failure_categories": {name: sum(r.get("failure_category") == name for r in real)
                                   for name in sorted({r.get("failure_category") for r in real if r.get("failure_category")})},
            "tasks": rows}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = score()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "harness_ok", "metrics", "failure_categories")},
                     indent=2))


if __name__ == "__main__":
    main()
