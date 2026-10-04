"""Fail-closed scorer for the final RD v3 formal tranche.

Only the frozen manifest, truth/reference files, sealed artifacts, machine tool
ledgers, and execution metadata are read.  Assistant prose is never interpreted.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[3]
TRUTH_TOOLS = ROOT / "experiments" / "rd" / "truth"
VERIFY_TOOLS = ROOT / "experiments" / "agent_verify"
for directory in (HERE, PARENT, TRUTH_TOOLS, VERIFY_TOOLS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import agreement  # noqa: E402
import graph  # noqa: E402
import resolver  # noqa: E402
from source import SourceSurface  # noqa: E402
from validity import agent_events  # noqa: E402

import rdv3_checkpoint as checkpoint  # noqa: E402
import rdv3_contract as contract  # noqa: E402
import rdv3_reference as reference  # noqa: E402
import rdv3_runner as runner  # noqa: E402


class ScoreError(RuntimeError):
    pass


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def metric(k: int, n: int, *, interval: bool = True) -> dict:
    return {"numerator": k, "denominator": n, "rate": round(k / n, 4) if n else None,
            "wilson95": wilson(k, n) if interval else None}


def conditional_metric(k: int, n: int) -> dict:
    if n == 0:
        return {**metric(k, n, interval=False), "status": "B_CONDITIONAL_NOT_ESTIMABLE"}
    if n < 3:
        return {**metric(k, n, interval=False), "rate": None,
                "status": "B_CONDITIONAL_UNDERPOWERED"}
    return {**metric(k, n), "status": "B_CONDITIONAL_ESTIMABLE"}


def _freeze(value):
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    return value


def _identity(anchor: dict):
    return _freeze(anchor.get("node_identity")) if isinstance(anchor, dict) else None


def _items(requirements: dict, prefix: str) -> list[dict]:
    rows = [{"id": f"{prefix}-entry", "kind": "entry", "entry": requirements["entry"]},
            {"id": f"{prefix}-behavior", "kind": "behavior",
             "behavior": requirements["behavior"]}]
    rows.extend({"id": f"{prefix}-q{number}", **copy.deepcopy(qualifier)}
                for number, qualifier in enumerate(requirements.get("required_qualifiers") or [], 1)
                if qualifier.get("kind") != "UNSUPPORTED_REQUIREMENT_TYPE")
    return rows


def score_a(task: dict, a: dict | None) -> dict:
    truth_requirements = reference.truth_requirements(task)
    truth_items = _items(truth_requirements, "truth")
    if a is None:
        counts = {}
        for kind in ("entry", "behavior", "qualifier"):
            truth_n = sum((row["kind"] if row["kind"] in ("entry", "behavior") else "qualifier")
                          == kind for row in truth_items)
            counts[kind] = {"truth": truth_n, "proposed": 0, "matched": 0}
        return {"counts": counts, "truth_matching": False,
                "unmatched_truth": [row["id"] for row in truth_items],
                "extra_qualifiers": []}

    source = SourceSurface(task["repo"], task["revisions"])
    provider = lambda revision, file: source.text(revision, file)
    truth_items = resolver.resolve_doc({"items": truth_items}, language=task["language"],
                                       source_provider=provider)["items"]
    agent_items = resolver.resolve_doc(
        {"items": _items(a["requirements"], "agent")}, language=task["language"],
        source_provider=provider)["items"]
    used, pairs = set(), []
    for truth in truth_items:
        identity = agreement.item_identity(truth, _identity)
        match = next((index for index, agent in enumerate(agent_items)
                      if index not in used and agreement.item_identity(agent, _identity) == identity), None)
        if match is not None:
            used.add(match)
            pairs.append((truth, agent_items[match]))
    matched_truth = {truth["id"] for truth, _ in pairs}
    matched_agent = {agent["id"] for _, agent in pairs}
    counts = {}
    for kind in ("entry", "behavior", "qualifier"):
        normalize = lambda row: row["kind"] if row["kind"] in ("entry", "behavior") else "qualifier"
        truth_rows = [row for row in truth_items if normalize(row) == kind]
        agent_rows = [row for row in agent_items if normalize(row) == kind]
        counts[kind] = {"truth": len(truth_rows), "proposed": len(agent_rows),
                        "matched": sum(truth in truth_rows and agent in agent_rows
                                       for truth, agent in pairs)}
    extra = [row["id"] for row in agent_items if row["kind"] not in ("entry", "behavior")
             and row["id"] not in matched_agent]
    return {"counts": counts,
            "pairs": [{"truth": truth["id"], "agent": agent["id"]}
                      for truth, agent in pairs],
            "truth_matching": matched_truth == {row["id"] for row in truth_items} and not extra,
            "unmatched_truth": sorted({row["id"] for row in truth_items} - matched_truth),
            "extra_qualifiers": extra}


def attribution(conclusion: dict, canonical_to_outward: dict[str, str]) -> tuple[str, dict]:
    canonical = {role: conclusion[outward] for role, outward in canonical_to_outward.items()}
    pair = (canonical["vuln"], canonical["fixed"])
    labels = {("SUPPORTED", "NOT_SUPPORTED"): "FIX_IMPLICATED",
              ("NOT_SUPPORTED", "SUPPORTED"): "CHANGE_IMPLICATED",
              ("SUPPORTED", "SUPPORTED"): "PRE_EXISTING",
              ("NOT_SUPPORTED", "NOT_SUPPORTED"): "NOT_SUPPORTED"}
    return labels.get(pair, "UNDETERMINED"), canonical


def _foreign_tools(stage_dir: Path) -> list[str]:
    names = set()
    for event in agent_events(stage_dir):
        if event.get("type") != "assistant":
            continue
        for content in (event.get("message") or {}).get("content", []):
            name = content.get("name", "")
            if content.get("type") == "tool_use" and not name.startswith("mcp__secreview__"):
                names.add(name)
    return sorted(names)


def _terminal_attempt(run_root: Path, task_id: str) -> Path | None:
    task_root = run_root / task_id
    attempts = sorted(task_root.glob("attempt-*")) if task_root.exists() else []
    complete = [path for path in attempts if (path / "attempt.json").exists()]
    terminal = [path for path in complete
                if json.loads((path / "attempt.json").read_text()).get("status") != "INFRA_INVALID"]
    return terminal[-1] if terminal else (complete[-1] if complete else None)


def _artifact(path: Path, problems: list[str], label: str) -> dict | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text())
        contract.verify_seal(value)
        return value
    except Exception as exc:
        problems.append(f"{label}: bad artifact/seal: {exc}")
        return None


def harness_problems(task: dict, attempt: Path, treatment: dict) -> list[str]:
    problems = []
    record_path = attempt / "attempt.json"
    if not record_path.exists():
        return ["missing terminal attempt record"]
    record = json.loads(record_path.read_text())
    if record.get("status") == "HARNESS_INVALID":
        problems.append(f"runner reported HARNESS_INVALID: {record.get('reason')}")
    attempted = {row.get("stage"): row for row in record.get("stages") or []}
    metas = {}
    for stage in runner.STAGES:
        stage_dir = attempt / f"stage-{stage}"
        meta_path = stage_dir / "meta.json"
        if not meta_path.exists():
            if stage in attempted and attempted[stage].get("status") not in ("BUDGET_CENSORED",):
                problems.append(f"{stage}: missing execution metadata")
            continue
        meta = json.loads(meta_path.read_text())
        metas[stage] = meta
        expected_timeout = 600 if stage == "c2" else runner.TIMEOUT[stage]
        if (meta.get("model"), meta.get("effort"), meta.get("claude_code_version"),
                meta.get("phase_budget_usd"), meta.get("max_budget_usd")) != (
                runner.MODEL, runner.EFFORT, runner.CLI_VERSION,
                runner.PHASE_BUDGET[stage], runner.SESSION_CAP[stage]):
            problems.append(f"{stage}: execution config drift")
        if not isinstance(meta.get("timeout"), (int, float)) or not 0 < meta["timeout"] <= expected_timeout:
            problems.append(f"{stage}: timeout envelope drift")
        env = meta.get("agent_environment") or {}
        cwd = env.get("cwd")
        if not cwd or Path(cwd).resolve().is_relative_to(ROOT):
            problems.append(f"{stage}: cwd not isolated")
        if env.get("model") != runner.MODEL:
            problems.append(f"{stage}: served model drift")
        expected_tools = {f"mcp__secreview__{name}" for name in runner.PHASE_TOOLS[stage]}
        if set(env.get("tools") or []) != expected_tools:
            problems.append(f"{stage}: exposed tool surface drift")
        if env.get("memory_files"):
            problems.append(f"{stage}: non-empty auto-memory")
        if _foreign_tools(stage_dir):
            problems.append(f"{stage}: foreign tools {_foreign_tools(stage_dir)}")
        ledger = stage_dir / "transcript.jsonl"
        if ledger.exists():
            for line in ledger.read_text().splitlines():
                event = json.loads(line)
                if event.get("tool") not in runner.PHASE_TOOLS[stage]:
                    problems.append(f"{stage}: unexpected server tool {event.get('tool')}")
                text = json.dumps(event)
                secrets = [str(ROOT), task.get("fixture", ""), *task["revisions"].values()]
                if any(secret and secret in text for secret in secrets):
                    problems.append(f"{stage}: context leak in tool ledger")
                if '"internal_error"' in text:
                    problems.append(f"{stage}: internal server error")
    if len(metas) > 1:
        if len({meta.get("agent_environment", {}).get("cwd") for meta in metas.values()}) != 1:
            problems.append("stage cwd changed")
        served = {meta.get("agent_environment", {}).get("served_session") for meta in metas.values()}
        if None in served or len(served) != 1:
            problems.append("stages did not resume one served session")
    if "c2" in metas:
        c1_seconds = float(metas.get("c1", {}).get("seconds", 0))
        c2_seconds = float(metas["c2"].get("seconds", 0))
        if c1_seconds + c2_seconds > 600.5:
            problems.append("C1+C2 exceeded the combined 600-second envelope")
        if abs(float(metas["c2"].get("c_envelope_elapsed_before", -1)) - c1_seconds) > 1.0:
            problems.append("C2 did not inherit the C1 elapsed-time clock")

    artifacts = attempt / "artifacts"
    a = _artifact(artifacts / "a.json", problems, "A")
    b = _artifact(artifacts / "b.json", problems, "B")
    terminal = _artifact(artifacts / "b-terminal.json", problems, "B terminal")
    partial = _artifact(artifacts / "partial-checkpoint.json", problems, "B checkpoint")
    c1 = _artifact(artifacts / "c1.json", problems, "C1")
    c2 = _artifact(artifacts / "c2.json", problems, "C2")
    expected_artifact = {"a": a, "b": b, "c1": c1, "c2": c2}
    for stage, stage_row in attempted.items():
        if stage_row.get("reason") == "locked" and expected_artifact.get(stage) is None:
            problems.append(f"{stage}: locked artifact was lost")
    if a and a.get("task_id") != task["task_id"]:
        problems.append("A belongs to another task")
    if b and terminal:
        problems.append("both final B and terminal-no-submit B exist")
    selected_b = b or terminal
    if selected_b and (not a or selected_b.get("a_seal") != a.get("seal")):
        problems.append("B does not bind locked A")
    if partial:
        try:
            with tempfile.TemporaryDirectory(prefix="rd-v3-score-checkpoint-") as tmp:
                reconstructed = checkpoint.materialize(
                    artifacts / "b-checkpoints", Path(tmp) / "partial-checkpoint.json")
                if reconstructed != partial:
                    problems.append("partial checkpoint does not match its event log")
        except Exception as exc:
            problems.append(f"checkpoint reconstruction failed: {exc}")
        for key in ("provider_sha256", "relation_table_sha256"):
            if partial.get(key) != treatment.get(key):
                problems.append(f"checkpoint {key} drift")
    if terminal and (not partial or terminal.get("partial_checkpoint_seal") != partial.get("seal")):
        problems.append("terminal B does not bind the partial checkpoint")
    if c1 and (not a or not selected_b or c1.get("a_seal") != a.get("seal")
               or c1.get("b_seal") != selected_b.get("seal")):
        problems.append("C1 does not bind locked A/B")
    if c2 and (not c1 or c2.get("c1_seal") != c1.get("seal")):
        problems.append("C2 does not bind locked C1")
    return sorted(set(problems))


def _continues(scorer: graph.GraphScorer, revision: str, left: tuple, right: tuple) -> bool:
    if left == right:
        return True
    connector = scorer.connectors[revision]
    return bool(connector and left[0] == right[0] == "node" and
                connector.same_object(left, right) == graph.connector.SAME)


def _longest(edges: list[dict], starts, next_predicate) -> int:
    best = 0
    for index, edge in enumerate(edges):
        if not starts(edge):
            continue
        stack = [(index, {index}, 1)]
        while stack:
            current, used, length = stack.pop()
            best = max(best, length)
            for nxt, candidate in enumerate(edges):
                if nxt not in used and next_predicate(edges[current], candidate):
                    stack.append((nxt, used | {nxt}, length + 1))
    return best


def checkpoint_diagnostics(scorer: graph.GraphScorer, a: dict, partial: dict) -> dict:
    b = {"hops": partial.get("checked_hops") or []}
    classification = scorer.classify(a, b)
    rows = {}
    for revision in contract.REVISIONS:
        edges, mismatches = scorer.edges(b, revision)
        entry = a["requirements"]["entry"][revision]
        behavior = a["requirements"]["behavior"][revision]
        if entry["state"] == "present":
            starts = scorer.anchor_nodes(revision, entry["anchor"], "from")
        else:
            starts = set()
        if behavior["state"] == "present":
            terminals = scorer.anchor_nodes(revision, behavior["anchor"], "to")
        else:
            terminals = set()
        follows = lambda left, right: _continues(scorer, revision, left["b"], right["a"])
        prefix = _longest(
            edges, lambda edge: any(_continues(scorer, revision, start, edge["a"])
                                    for start in starts), follows)
        suffix = _longest(
            edges, lambda edge: any(_continues(scorer, revision, edge["b"], terminal)
                                    for terminal in terminals),
            lambda right, left: follows(left, right))
        adjacency = {index: set() for index in range(len(edges))}
        for left in range(len(edges)):
            for right in range(left + 1, len(edges)):
                if follows(edges[left], edges[right]) or follows(edges[right], edges[left]):
                    adjacency[left].add(right)
                    adjacency[right].add(left)
        largest = 0
        unseen = set(adjacency)
        while unseen:
            seed = unseen.pop()
            component, frontier = {seed}, [seed]
            while frontier:
                node = frontier.pop()
                added = adjacency[node] & unseen
                unseen -= added
                component |= added
                frontier.extend(added)
            largest = max(largest, len(component))
        qualifiers = a["requirements"].get("required_qualifiers") or []
        applicable = [qualifier for qualifier in qualifiers
                      if qualifier.get("kind") != "UNSUPPORTED_REQUIREMENT_TYPE" and
                      scorer._qualifier_anchors({"required_qualifiers": [qualifier]}, revision)]
        attached = 0
        for qualifier in applicable:
            one = copy.deepcopy(a)
            one["requirements"]["required_qualifiers"] = [copy.deepcopy(qualifier)]
            if scorer.classify(one, b)["revisions"][revision]["class"] == "FULL_CHAIN":
                attached += 1
        rows[revision] = {
            "verified_edges": len(edges), "largest_connected_component_edges": largest,
            "longest_verified_entry_prefix": prefix,
            "longest_verified_terminal_suffix": suffix,
            "terminal_reach": any(any(_continues(scorer, revision, edge["b"], terminal)
                                      for terminal in terminals) for edge in edges),
            "qualifier_attachments": attached, "qualifier_obligations": len(applicable),
            "harness_mismatches": mismatches,
        }
    return {"event_count": partial.get("event_count"),
            "last_successful_event": partial.get("last_successful_event"),
            "checkpoint_already_full_chain": classification["full_chain"],
            "revisions": rows}


def score_task(task: dict, run_root: Path, treatment: dict) -> tuple[dict, list[str]]:
    attempt = _terminal_attempt(run_root, task["task_id"])
    row = {"task_id": task["task_id"], "task_kind": task["task_kind"],
           "fixture": task.get("fixture")}
    if attempt is None:
        row.update({"status": "MISSING", "stages_locked": []})
        if task["task_kind"] == "real":
            row["a"] = score_a(task, None)
            ref = json.loads(Path(task["reference_result_path"]).read_text())
            row["reference_disposition"] = ref.get("disposition")
            row["correct_verified_implementation"] = False
        return row, []
    problems = harness_problems(task, attempt, treatment)
    record = json.loads((attempt / "attempt.json").read_text())
    artifacts = attempt / "artifacts"
    locked = {name: value for name in ("a", "b", "partial-checkpoint", "b-terminal", "c1", "c2")
              if (value := _artifact(artifacts / f"{name}.json", problems, name)) is not None}
    row.update({"attempt": attempt.name, "run_status": record.get("status"),
                "run_reason": record.get("reason"), "stages_locked": sorted(locked)})
    a = locked.get("a")
    if task["task_kind"] == "real":
        try:
            row["a"] = score_a(task, a)
        except Exception as exc:
            problems.append(f"A scoring failed: {exc}")
    if a and locked.get("partial-checkpoint"):
        try:
            scorer = graph.GraphScorer(
                language=task["language"], repo=task["repo"], revisions=task["revisions"],
                analysis=graph.load_analysis(task["analysis"]))
            row["b_checkpoint"] = checkpoint_diagnostics(
                scorer, a, locked["partial-checkpoint"])
            if any(item["harness_mismatches"]
                   for item in row["b_checkpoint"]["revisions"].values()):
                problems.append("checkpoint graph has verifier mismatches")
            if locked.get("b"):
                row["b"] = scorer.classify(a, locked["b"])
                if row["b"]["harness_mismatches"]:
                    problems.append("final B graph has verifier mismatches")
        except Exception as exc:
            problems.append(f"B scoring failed: {exc}")
    c1 = locked.get("c1")
    if c1:
        try:
            label, canonical = attribution(c1["conclusion"], task["canonical_to_outward"])
            row["c1"] = {"canonical_statuses": canonical, "attribution": label,
                         "expected": task["expected_attribution"],
                         "correct": label == task["expected_attribution"]}
        except Exception as exc:
            problems.append(f"C1 scoring failed: {exc}")
    c2 = locked.get("c2")
    if c2:
        taxonomy = c2["taxonomy"]
        ranked = taxonomy.get("ranked_cwes") or []
        target = task["taxonomy_target"]
        row["c2"] = {"target": target, "ranked_cwes": ranked,
                     "no_confident_cwe": taxonomy.get("result") == "NO_CONFIDENT_CWE",
                     "top1_agreement": bool(ranked) and ranked[0] == target,
                     "top3_agreement": target in ranked}
    if task["task_kind"] == "real":
        ref = json.loads(Path(task["reference_result_path"]).read_text())
        if ref.get("task_id") != task["task_id"] or ref.get("disposition") not in (
                reference.FULL, reference.BLIND, reference.UNREALIZABLE):
            problems.append("invalid or foreign reference result")
        row["reference_disposition"] = ref.get("disposition")
        a_ok = (row.get("a") or {}).get("truth_matching", False)
        b_full = bool((row.get("b") or {}).get("full_chain"))
        row["correct_verified_implementation"] = a_ok and b_full
        c_ok = bool((row.get("c1") or {}).get("correct"))
        if not a_ok:
            row["failure_category"] = "A_WRONG_C_CORRECT" if c_ok else "A_WRONG"
        elif b_full:
            row["failure_category"] = "A_B_C1_CORRECT" if c_ok else "A_B_CORRECT_C1_WRONG"
        elif row["reference_disposition"] == reference.UNREALIZABLE:
            row["failure_category"] = reference.UNREALIZABLE
        elif row["reference_disposition"] == reference.BLIND:
            row["failure_category"] = "A_CORRECT_PROVIDER_BLIND"
        elif locked.get("b") is None:
            row["failure_category"] = "A_CORRECT_NO_FINAL_B_SUBMIT"
        else:
            row["failure_category"] = "A_CORRECT_B_INCOMPLETE"
    return row, sorted(set(problems))


def score(manifest_path: Path) -> dict:
    manifest = runner.load_manifest(manifest_path)
    if manifest["mode"] != "formal":
        raise ScoreError("formal scorer requires a formal manifest")
    if not runner.TREATMENT_FREEZE.exists() \
            or runner.sha256(runner.TREATMENT_FREEZE) != manifest.get("treatment_freeze_sha256"):
        raise ScoreError("treatment freeze is missing or does not match the manifest")
    treatment = json.loads(runner.TREATMENT_FREEZE.read_text())
    if treatment.get("status") != "TREATMENT_FROZEN":
        raise ScoreError("treatment freeze is not in TREATMENT_FROZEN state")
    run_root = runner.RUNS / "formal"
    rows, harness = [], {}
    for task in manifest["tasks"]:
        task_row, problems = score_task(task, run_root, treatment)
        rows.append(task_row)
        if problems:
            harness[task["task_id"]] = problems
    expected_ids = [task["task_id"] for task in manifest["tasks"]]
    observed_ids = [path.name for path in run_root.iterdir() if path.is_dir()] if run_root.exists() else []
    extras = sorted(set(observed_ids) - set(expected_ids))
    if extras:
        harness["__manifest__"] = [f"unmanifested task directories: {extras}"]

    real = [row for row in rows if row["task_kind"] == "real"]
    controls = [row for row in rows if row["task_kind"] == "negative_control"]
    a_metrics = {}
    for kind in ("entry", "behavior", "qualifier"):
        matched = sum((row.get("a") or {}).get("counts", {}).get(kind, {}).get("matched", 0)
                      for row in real)
        truth_n = sum((row.get("a") or {}).get("counts", {}).get(kind, {}).get("truth", 0)
                      for row in real)
        proposed = sum((row.get("a") or {}).get("counts", {}).get(kind, {}).get("proposed", 0)
                       for row in real)
        a_metrics[kind] = {"recall": metric(matched, truth_n),
                           "precision": metric(matched, proposed)}
    conditional = [row for row in real if row.get("reference_disposition") == reference.FULL]
    b_agent_all = sum(bool((row.get("b") or {}).get("full_chain")) for row in real)
    b_correct_all = sum(bool(row.get("correct_verified_implementation")) for row in real)
    b_agent_cond = sum(bool((row.get("b") or {}).get("full_chain")) for row in conditional)
    b_correct_cond = sum(bool(row.get("correct_verified_implementation")) for row in conditional)
    false_supported = sum(status == "SUPPORTED" for row in controls
                          for status in (row.get("c1") or {}).get("canonical_statuses", {}).values())
    c2_rows = [row.get("c2") for row in rows]
    unfinished = any(row.get("status") == "MISSING" or
                     row.get("run_status") in ("INFRA_INVALID", "BUDGET_CENSORED") for row in rows)
    status = "HARNESS_INVALID" if harness else ("RUN_INCOMPLETE" if unfinished else "REPORTED")
    return {
        "schema": "rd-v3-score/v1", "protocol": runner.PROTOCOL, "status": status,
        "harness_ok": not harness, "harness_problems": harness,
        "reference_coverage": {
            disposition: sum(row.get("reference_disposition") == disposition for row in real)
            for disposition in (reference.FULL, reference.BLIND, reference.UNREALIZABLE)},
        "metrics": {
            "a": a_metrics,
            "b_system_agent_full_chain": metric(b_agent_all, len(real)),
            "b_system_correct_verified": metric(b_correct_all, len(real)),
            "b_conditional_agent_full_chain": conditional_metric(b_agent_cond, len(conditional)),
            "b_conditional_correct_verified": conditional_metric(b_correct_cond, len(conditional)),
            "c1_real_attribution_accuracy": metric(
                sum(bool((row.get("c1") or {}).get("correct")) for row in real), len(real)),
            "c1_negative_control_false_supported_rate": metric(
                false_supported, 2 * len(controls)),
            "c2_top1_frozen_label_agreement": metric(
                sum(bool(row and row.get("top1_agreement")) for row in c2_rows), len(rows)),
            "c2_top3_frozen_label_agreement": metric(
                sum(bool(row and row.get("top3_agreement")) for row in c2_rows), len(rows)),
            "c2_no_confident_cwe_rate": metric(
                sum(bool(row and row.get("no_confident_cwe")) for row in c2_rows), len(rows)),
            "c1_missing": sum("c1" not in row for row in rows),
            "c2_not_reached": sum("c1" not in row for row in rows),
            "c2_missing_after_c1": sum("c1" in row and "c2" not in row for row in rows),
        },
        "failure_categories": {
            name: sum(row.get("failure_category") == name for row in real)
            for name in sorted({row.get("failure_category") for row in real
                                if row.get("failure_category")})},
        "tasks": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = score(args.manifest)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "status", "harness_ok", "reference_coverage", "metrics", "failure_categories")}, indent=2))


if __name__ == "__main__":
    main()
