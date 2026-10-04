"""Spike 1B scorer: grade runs against goldens and compute the pre-registered metrics.

    uv run python experiments/agent_verify/score.py fixtures/synthetic-notes/case.yaml \
        [--protocol v1] [--out results/1b-stage1-haiku.json]

Reads runs/agent_verify/<protocol>/<case>/<hyp>/<condition>/<agent_model>/r<k>/,
writes score.json into each run directory and the summary (with every per-run
score and the scorer's provenance) to --out, default
runs/agent_verify/<protocol>/score.json. Metric definitions: PREREGISTRATION.md §4.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from validity import INFRA_INVALID, agent_events, classify, served_models

from spike.anchors import Anchor, verify
from spike.derive import derive
from spike.gitrepo import GitRepo
from spike.golden import check_golden, expected
from spike.linemap import LineMap
from spike.models import CaseSpec, Fact, Golden, Observation, SessionConfig

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs" / "agent_verify"
RUN_DIR_NAME = re.compile(r"^r\d+$")  # archived invalid attempts (r0.invalid1, ...) are skipped

CITATION_ERRORS = ("unknown_anchor", "quote_not_found", "quote_ambiguous", "quote_empty")
HARNESS_ERRORS = ("internal_error", "git_error")
# Screening only: on identical code, talk of change is a change-bias symptom worth reading.
CHANGE_LANGUAGE = re.compile(
    r"\b(remov|introduc|add(ed|s)\b|no longer|chang|refactor|moved|regress|previously|"
    r"before the change|after the change|was replaced)",
    re.IGNORECASE,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def foreign_tool_use(events: list[dict]) -> list[str]:
    """Anything the agent did outside the secreview MCP server."""
    found = []
    for event in events:
        if event.get("type") == "assistant":  # claude stream-json
            for block in event["message"].get("content", []):
                name = block.get("name", "")
                if block.get("type") == "tool_use" and not name.startswith("mcp__secreview"):
                    found.append(name)
        item = event.get("item") or {}
        if item.get("type") in ("command_execution", "file_change", "web_search"):  # codex
            found.append(item["type"])
    return found


ARM_TOKEN = re.compile(r"_(control|treatment)\b")


def context_leaks(
    events: list[dict], run_dir: Path | None = None, transcript: list[dict] = ()
) -> list[str]:
    """Harness state that could reach the agent's context (PREREGISTRATION.md §2.1, §8.1).

    Besides the cwd and auto-memory, the run's own label (which carries the A/B
    arm) and its run directory must appear neither in what the CLI reports about
    the agent's context nor in any tool result the agent received. The bare arm
    words are only checked in that CLI context: tool results are source code,
    where an identifier like `cache_control` is not a leak.
    """
    init = next(
        (e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {}
    )
    leaks = []
    if run_dir is not None:
        label, runs_root = run_dir.parent.name, str(RUNS)
        init_text = json.dumps(init)
        if label in init_text or runs_root in init_text or ARM_TOKEN.search(init_text):
            leaks.append("run_identity_in_init")
        results_text = json.dumps([e.get("result") for e in transcript])
        if label in results_text or runs_root in results_text:
            leaks.append("run_identity_in_tool_results")
    cwd = init.get("cwd")
    if cwd and Path(cwd).resolve().is_relative_to(ROOT):
        leaks.append("cwd_inside_harness_repo")
    memory_dir = (init.get("memory_paths") or {}).get("auto")
    if memory_dir and Path(memory_dir).is_dir() and any(Path(memory_dir).iterdir()):
        leaks.append("auto_memory_not_empty")
    return leaks


def fact_covered(fact: Fact, citations: list[Anchor]) -> bool:
    def cited(loc) -> bool:
        lo, hi = loc.span()
        return any(
            a.revision == fact.revision
            and a.path == loc.path
            and a.start_line <= hi
            and lo <= a.end_line
            for a in citations
        )

    return any(all(cited(loc) for loc in evidence_set) for evidence_set in fact.evidence_sets)


def score_run(run_dir: Path, golden: Golden, runs_root: Path) -> dict:
    hyp_id, condition, agent, _repeat = run_dir.parts[-4:]
    g = golden.hypotheses[hyp_id]
    validity, outcome = classify(run_dir)
    meta = json.loads((run_dir / "meta.json").read_text())
    result: dict = {
        "run": str(run_dir.relative_to(runs_root)),
        "case": golden.case,
        "hypothesis": hyp_id,
        "condition": condition,
        "agent": agent,
        "negative_control": not any(g.truth.values()),
        "validity": validity,
        "outcome": outcome,
        "attempt": meta.get("attempt", 1),
    }
    if validity == INFRA_INVALID:
        (run_dir / "score.json").write_text(json.dumps(result, indent=2))
        return result

    session = SessionConfig.model_validate_json((run_dir / "session.json").read_text())
    state = json.loads((run_dir / "state.json").read_text())
    exp = expected(g, condition)
    repo = GitRepo(session.repo)
    linemap = LineMap(repo, state["commits"]["base"], state["commits"]["head"])
    observations = [Observation(**o) for o in state["observations"]]
    got = derive(observations, list(g.components), linemap)

    cells = [(s, c) for s in ("base", "head") for c in g.components]
    correct = sum(got["components"][s][c] == exp["components"][s][c] for s, c in cells)

    log = run_dir / "transcript.jsonl"  # absent when the agent never called a tool
    transcript = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
    errors = Counter(e["error"]["code"] for e in transcript if "error" in e)
    submits = sum(e["tool"] in ("submit_observation", "submit_blind_spot") for e in transcript)

    audit_failures = 0
    for record in state["anchors"]:
        blob = repo.read_blob(record.pop("commit"), record["path"])
        lines = blob.decode("utf-8", errors="replace").splitlines() if blob else []
        audit_failures += not verify(Anchor(**record), lines)

    citations = [a for o in observations for a in o.citations]
    facts = {f.id: fact_covered(f, citations) for f in exp["facts"]}
    attribution_correct = got["attribution"] == exp["attribution"]
    events = agent_events(run_dir)
    result_event = next((e for e in reversed(events) if e.get("type") == "result"), {})

    result |= {
        "finished": state["finished"],
        "served_models": served_models(run_dir),
        "component_accuracy": correct / len(cells),
        "revisions": got["revisions"],
        "false_supported_revisions": [
            side
            for side in ("base", "head")
            if got["revisions"][side] == "SUPPORTED" and exp["revisions"][side] != "SUPPORTED"
        ],
        "unsupported_revisions_expected": sum(v != "SUPPORTED" for v in exp["revisions"].values()),
        "attribution": got["attribution"],
        "expected_attribution": exp["attribution"],
        "attribution_correct": attribution_correct,
        "facts_covered": facts,
        "fact_coverage": mean(facts.values()) if facts else None,
        "evidence_complete_correct": attribution_correct and all(facts.values()),
        "submissions": submits,
        "errors": dict(errors),
        "citation_errors": sum(errors[c] for c in CITATION_ERRORS),
        "revision_mismatches": errors["revision_mismatch"],
        "harness_errors": sum(errors[c] for c in HARNESS_ERRORS),
        "anchor_audit_failures": audit_failures,
        "accepted_revision_mismatches": sum(
            a.revision != o.revision for o in observations for a in o.citations
        ),
        "blind_spots": len(state["blind_spots"]),
        "tool_calls": len(transcript),
        "foreign_tools": foreign_tool_use(events),
        "context_leaks": context_leaks(events, run_dir, transcript),
        "api_key_source": next(
            (e.get("apiKeySource") for e in events if e.get("subtype") == "init"), None
        ),
        "cost_usd": result_event.get("total_cost_usd"),
        "components": got["components"],
    }
    if condition.startswith("identity"):
        agreement = [
            got["components"]["base"][c] == got["components"]["head"][c] for c in g.components
        ]
        result["identity_inconsistent"] = [c for c, same in zip(g.components, agreement) if not same]
        result["identity_component_agreement"] = mean(agreement)
        result["identity_change_language"] = [
            o.id for o in observations if CHANGE_LANGUAGE.search(o.statement)
        ]
    (run_dir / "score.json").write_text(json.dumps(result, indent=2))
    return result


def _majority(values: list) -> tuple[object, float]:
    top, count = Counter(values).most_common(1)[0]
    return top, count / len(values)


def _mean(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return mean(values) if values else None


def summarize(all_scores: list[dict]) -> dict:
    invalid = [s for s in all_scores if s["validity"] == INFRA_INVALID]
    scores = [s for s in all_scores if s["validity"] != INFRA_INVALID]
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for s in scores:
        groups[(s["case"], s["hypothesis"], s["condition"], s["agent"])].append(s)

    cells = {}
    for key, runs in sorted(groups.items()):
        attribution, agreement = _majority([r["attribution"] for r in runs])
        cells["/".join(key)] = {
            "n": len(runs),
            "finished": mean(r["finished"] for r in runs),
            "component_accuracy": round(mean(r["component_accuracy"] for r in runs), 3),
            "fact_coverage": _mean([r["fact_coverage"] for r in runs]),
            "attribution_majority": attribution,
            "attribution_agreement": round(agreement, 3),
            "attribution_correct": round(mean(r["attribution_correct"] for r in runs), 3),
            "evidence_complete_correct": round(
                mean(r["evidence_complete_correct"] for r in runs), 3
            ),
            "expected_attribution": runs[0]["expected_attribution"],
        }

    # Swapped runs should mirror forward runs component by component. Repeats are
    # independent, so majorities are compared; runs are never paired by index.
    mirror = []
    for (case, hyp, cond, agent), runs in groups.items():
        if cond != "swapped" or (case, hyp, "forward", agent) not in groups:
            continue
        fwd = groups[(case, hyp, "forward", agent)]
        for comp in runs[0]["components"]["base"]:
            for side, other in (("base", "head"), ("head", "base")):
                a, _ = _majority([r["components"][side][comp] for r in fwd])
                b, _ = _majority([r["components"][other][comp] for r in runs])
                mirror.append(a == b)

    neg = [s for s in scores if s["negative_control"]]
    identity = [s for s in scores if "identity_inconsistent" in s]
    submissions = sum(s["submissions"] for s in scores) or 1
    # Any non-zero value here (bar the infra-invalid rate, capped in §1.2) is a harness bug.
    invariants = {
        "anchor_audit_failures": sum(s["anchor_audit_failures"] for s in scores),
        "accepted_revision_mismatches": sum(s["accepted_revision_mismatches"] for s in scores),
        "harness_errors": sum(s["harness_errors"] for s in scores),
        "runs_with_foreign_tools": sum(bool(s["foreign_tools"]) for s in scores),
        "runs_with_context_leak": sum(bool(s["context_leaks"]) for s in scores),
        "infra_invalid_slots": len(invalid),
        "infra_invalid_rate": len(invalid) / len(all_scores),
    }
    if not scores:
        return {"harness_invariants": invariants, "metrics": {}, "cells": {}}
    metrics = {
        "valid_runs": len(scores),
        "outcomes": dict(Counter(s["outcome"] for s in scores)),
        "finished_rate": mean(s["finished"] for s in scores),
        "attribution_correct_rate": mean(s["attribution_correct"] for s in scores),
        "attribution_correct_rate_forward": _mean(
            [s["attribution_correct"] for s in scores if s["condition"] == "forward"]
        ),
        "evidence_complete_correct_rate": mean(s["evidence_complete_correct"] for s in scores),
        "fact_coverage": _mean([s["fact_coverage"] for s in scores]),
        "fact_coverage_by_condition": {
            cond: _mean([s["fact_coverage"] for s in scores if s["condition"] == cond])
            for cond in ("forward", "swapped", "identity_base", "identity_head")
        },
        "component_accuracy": mean(s["component_accuracy"] for s in scores),
        "negative_control_false_supported_rate": _mean(
            [any(v == "SUPPORTED" for v in s["revisions"].values()) for s in neg]
        ),
        "false_supported_revision_rate": (
            sum(len(s["false_supported_revisions"]) for s in scores)
            / (sum(s["unsupported_revisions_expected"] for s in scores) or 1)
        ),
        "forward_correct_by_true_hypothesis": {
            "/".join(k[:2]): round(mean(r["attribution_correct"] for r in runs), 3)
            for k, runs in sorted(groups.items())
            if k[2] == "forward" and not runs[0]["negative_control"]
        },
        "repeat_agreement": mean(c["attribution_agreement"] for c in cells.values()),
        "swap_mirror_consistency": _mean(mirror),
        "identity_inconsistency_rate": _mean([bool(s["identity_inconsistent"]) for s in identity]),
        "identity_component_agreement": _mean(
            [s["identity_component_agreement"] for s in identity]
        ),
        "identity_runs_with_change_language": (
            sum(bool(s["identity_change_language"]) for s in identity) if identity else None
        ),
        "attempt_citation_error_rate": sum(s["citation_errors"] for s in scores) / submissions,
        "runs_with_attempted_revision_mismatch": mean(
            s["revision_mismatches"] > 0 for s in scores
        ),
        "served_models": sorted({m for s in scores for m in s["served_models"]}),
        "api_key_sources": sorted({str(s["api_key_source"]) for s in scores}),
        "cost_usd": sum(s["cost_usd"] or 0 for s in scores),
    }
    return {"harness_invariants": invariants, "metrics": metrics, "cells": cells}


def provenance(case_paths: list[Path]) -> dict:
    def git(*args: str) -> str:
        out = subprocess.run(
            ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=False
        )
        return out.stdout.strip()

    return {
        "scored_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "harness_commit": git("rev-parse", "--verify", "-q", "HEAD") or None,
        "harness_dirty": bool(git("status", "--porcelain")),
        "scorer_sha256": sha256(Path(__file__)),
        "goldens_sha256": {
            str(p.parent / "golden.yaml"): sha256(p.parent / "golden.yaml") for p in case_paths
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("cases", nargs="+", type=Path)
    ap.add_argument("--protocol", default="v1")
    ap.add_argument("--out", type=Path, help="where to write the summary")
    ap.add_argument("--label", default="*",
                    help="only runs whose agent label matches this glob, e.g. '*_treatment'")
    args = ap.parse_args()
    runs_root = RUNS / args.protocol

    scores = []
    for case_path in args.cases:
        case = CaseSpec.load(case_path)
        golden = Golden.load(case_path.parent / "golden.yaml")
        if problems := check_golden(golden):
            raise SystemExit("\n".join(problems))
        for session in sorted((runs_root / case.id).glob(f"*/*/{args.label}/r*/session.json")):
            run_dir = session.parent
            if RUN_DIR_NAME.match(run_dir.name) and (run_dir / "meta.json").exists():
                scores.append(score_run(run_dir, golden, runs_root))
    if not scores:
        raise SystemExit("no attempted runs found")

    summary = {"provenance": provenance(args.cases), **summarize(scores), "runs": scores}
    out = args.out or runs_root / "score.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))
    for section in ("harness_invariants", "metrics"):
        print(f"[{section}]")
        for k, v in summary[section].items():
            print(f"  {k:40} {round(v, 3) if isinstance(v, float) else v}")
    print()
    for key, c in summary["cells"].items():
        flag = "" if c["attribution_majority"] == c["expected_attribution"] else "  ✗"
        coverage = "-" if c["fact_coverage"] is None else f"{c['fact_coverage']:.2f}"
        print(
            f"{key:64} n={c['n']} comp={c['component_accuracy']:.2f} facts={coverage} "
            f"attr={c['attribution_majority']}({c['attribution_agreement']:.0%}) "
            f"expect={c['expected_attribution']}{flag}"
        )
    print(f"\nsummary written to {out}")


if __name__ == "__main__":
    main()
