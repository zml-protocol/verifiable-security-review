"""§13 Completeness Repair scoring (PREREGISTRATION.md §13.4-13.6).

    uv run python experiments/hop_repair/repair_score.py --out results/completeness-repair.json
    uv run python experiments/hop_repair/repair_score.py --pilot --out runs/hop_repair/pilot.json

"Complete" is exactly the frozen §12 classifier's FULL_CHAIN at both revisions (frozen
verifier rows, calibrated same-object connector, rule-G anchors, guard qualifier).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for sub in ("hop_propose", "hop_chain"):
    sys.path.insert(0, str(ROOT / "experiments" / sub))
sys.path.insert(0, str(HERE))

import chain
import connector as C
import power
import propose_score as S
import replicate_score as CS

PROTOCOL = "r1"
PRIMARY = ("caddy-forward-auth", "filebrowser-archive-backslash")
SANITY = ("authlib-jws-none",)
K_ELIGIBLE = 12   # complete eligible pairs per primary fixture (§13.5)
M_INITIALS = 30   # VALID initial sessions per primary fixture at most
N_SANITY = 5      # VALID initial sessions for the ceiling fixture
ARMS = ("control", "treatment")
# §13.1: the formal execution configuration, exactly what all 45 P-Hybrid-2 sessions recorded
# (meta.json) and were served (init event); only the contract and the one sentence differ.
FORMAL = {"model": "claude-sonnet-5", "effort": "high", "max_budget_usd": 3.0, "timeout": 1200}
FORMAL_SERVED = {"model": "claude-sonnet-5", "claude_code_version": "2.1.280"}


def config_problems(run_dir: Path) -> list[str]:
    """How one formal run deviates from the frozen execution configuration."""
    meta = json.loads((run_dir / "meta.json").read_text())
    out = [f"{k}={meta.get(k)!r}" for k, v in FORMAL.items() if meta.get(k) != v]
    init = next((e for e in S.R.agent_events(run_dir)
                 if e.get("type") == "system" and e.get("subtype") == "init"), None)
    if init is not None:
        out += [f"served {k}={init.get(k)!r}" for k, v in FORMAL_SERVED.items() if init.get(k) != v]
    return out


def runs_root(pilot: bool) -> Path:
    return ROOT / "runs" / "hop_repair" / (f"{PROTOCOL}-pilot" if pilot else PROTOCOL)


def fixtures(pilot: bool) -> tuple[str, ...]:
    return tuple(sorted(S.R.CASES["pilot"])) if pilot else PRIMARY + SANITY


_MATCHERS: dict[tuple[str, bool], S.Matcher] = {}


def classify_submission(fixture: str, hops: list[dict] | None, pilot: bool) -> dict:
    """The frozen §12 classification of one submission at both revisions."""
    m = _MATCHERS.setdefault((fixture, pilot), S.Matcher(fixture, pilot))
    anchors = CS.anchors(pilot)[fixture]
    revisions, rejected = {}, []
    for rev in ("base", "head"):
        edges, bad = CS.revision_edges(m, hops or [], rev)
        rejected += [f"{rev}:{h}" for h in bad]
        conn = C.load_frozen(fixture, rev) if m.entry["language"] == "go" else None
        if m.entry["language"] == "go" and conn is None:
            raise RuntimeError(f"no connector rows for {fixture} {rev}")
        same = (lambda a, b, c=conn: c.same_object(a, b) == C.SAME) if conn else None
        a = anchors[rev]
        revisions[rev] = {**chain.classify(edges, a["entry"], a["terminal"], a["needs_qualifier"],
                                           same), "verified_edges": len(edges)}
    sub = m.submission(hops or [])
    return {"revisions": revisions,
            "full": all(r["class"] == "FULL_CHAIN" for r in revisions.values()),
            "rejected": rejected, "hops": sub["n"], "unsupported": sub["unsupported"],
            "verified": sub["verified"]}


def outcome(control_full: bool, treatment_full: bool) -> str:
    return {(False, True): "T_only", (True, False): "C_only",
            (True, True): "Both", (False, False): "Neither"}[(control_full, treatment_full)]


def blocks_on_disk(pilot: bool, fixture: str) -> list[Path]:
    d = runs_root(pilot) / fixture
    return sorted((p for p in d.glob("i*") if p.name[1:].isdigit()), key=lambda p: int(p.name[1:])) \
        if d.exists() else []


def block_record(block: Path, fixture: str, pilot: bool) -> dict:
    parent = block / "initial"
    rec = {"block": f"{fixture}/{block.name}", "fixture": fixture}
    rec["parent"] = S.R.classify(parent) if (parent / "meta.json").exists() else ("MISSING", "not_run")
    if rec["parent"][0] != "VALID":
        return rec
    initial = classify_submission(fixture, S.state_of(parent)["initial"], pilot)
    rec["initial"] = initial
    recorded = json.loads((block / "initial_class.json").read_text()) if (block / "initial_class.json").exists() else None
    rec["runtime_eligibility_matches"] = recorded is None or recorded["full"] == initial["full"]
    rec["eligible"] = not initial["full"]
    forked = (block / "isolation.json").exists()
    rec["forked"] = forked
    if not forked:
        return rec
    rec["children"] = {arm: (S.R.classify(block / arm) if (block / arm / "meta.json").exists()
                             else ("MISSING", "not_run")) for arm in ARMS}
    if all(v[0] == "VALID" for v in rec["children"].values()):
        rec["finals"] = {arm: classify_submission(fixture, S.state_of(block / arm)["final"], pilot)
                         for arm in ARMS}
        rec["outcome"] = outcome(rec["finals"]["control"]["full"], rec["finals"]["treatment"]["full"])
    return rec


def sampling_counts(records: list[dict]) -> dict:
    valid = [r for r in records if r["parent"][0] == "VALID"]
    return {"valid_initials": len(valid),
            "initially_full": sum(1 for r in valid if not r["eligible"]),
            "eligible": sum(1 for r in valid if r["eligible"]),
            "complete_pairs": sum(1 for r in valid if r["eligible"] and "outcome" in r)}


def done(fixture: str, counts: dict, pilot: bool) -> bool:
    """§13.4 stopping rule; depends only on pre-treatment covariates (initial completeness)
    and on how many pairs completed, never on arm outcomes."""
    if pilot:
        return counts["valid_initials"] >= 1
    if fixture in SANITY:
        return counts["valid_initials"] >= N_SANITY
    return counts["complete_pairs"] >= K_ELIGIBLE or counts["valid_initials"] >= M_INITIALS


def decide(harness_ok: bool, pilot: bool, per_fixture: dict,
           config_mismatch: bool = False) -> tuple[str, dict, dict]:
    """§13.6, in order: PROTOCOL_INVALID (a run left the frozen execution configuration),
    HARNESS_INVALID, RUN_INCOMPLETE (a fixture reached neither its target nor its cap),
    INCONCLUSIVE_OPPORTUNITY (cap reached, target not), then SUCCESS or FAIL."""
    primary = [f for f in (PRIMARY if not pilot else ()) if f in per_fixture]
    t = sum(per_fixture[f]["outcomes"]["T_only"] for f in primary)
    c = sum(per_fixture[f]["outcomes"]["C_only"] for f in primary)
    criteria = {"pooled_sign_test_p": power.sign_p(t, c),
                "pooled_significant": power.sign_p(t, c) <= power.ALPHA,
                "each_fixture_T_only_at_least_C_only": all(
                    per_fixture[f]["outcomes"]["T_only"] >= per_fixture[f]["outcomes"]["C_only"]
                    for f in primary)}
    if config_mismatch:
        status = "PROTOCOL_INVALID"
    elif not harness_ok:
        status = "HARNESS_INVALID"
    elif pilot:
        status = "PILOT"
    elif not all(per_fixture.get(f, {}).get("reached_target") for f in PRIMARY + SANITY):
        status = "RUN_INCOMPLETE"
    elif not all(per_fixture.get(f, {}).get("opportunity_met") for f in PRIMARY):
        status = "INCONCLUSIVE_OPPORTUNITY"
    else:
        status = "SUCCESS" if criteria["pooled_significant"] and \
            criteria["each_fixture_T_only_at_least_C_only"] else "FAIL"
    return status, criteria, {"T_only": t, "C_only": c}


def score(pilot: bool) -> dict:
    problems = C.rows_problems("pilot" if pilot else "eval") + ([] if pilot else C.gate())
    if problems:
        return {"protocol": PROTOCOL, "pilot": pilot, "status": "PROTOCOL_INVALID",
                "problems": problems}
    harness = {"context_leak": {}, "foreign_tools": {}, "harness_errors": 0, "isolation": {},
               "locked_hop_rejected": {}, "eligibility_mismatch": []}
    config_mismatch: dict[str, list[str]] = {}
    per_fixture, all_records = {}, []
    for fixture in fixtures(pilot):
        records = [block_record(b, fixture, pilot) for b in blocks_on_disk(pilot, fixture)]
        all_records += records
        for r in records:
            block = runs_root(pilot) / r["block"]
            if r["parent"][0] != "VALID":
                continue
            dirs = ["initial"] + ([a for a in ARMS if (block / a / "meta.json").exists()]
                                  if r.get("forked") else [])
            for d in dirs:
                if not pilot and (bad_config := config_problems(block / d)):
                    config_mismatch[f"{r['block']}/{d}"] = bad_config
                if found := S.leaks(block / d, block):
                    harness["context_leak"][f"{r['block']}/{d}"] = found
                if tools := S.foreign_tools(block / d):
                    harness["foreign_tools"][f"{r['block']}/{d}"] = tools
                harness["harness_errors"] += S.harness_errors(block / d)
            if r.get("forked") and (iso := S.isolation_problems(block)):
                harness["isolation"][r["block"]] = iso
            subs = [r["initial"], *(r.get("finals", {}).values())]
            if bad := [x for s in subs for x in s["rejected"]]:
                harness["locked_hop_rejected"][r["block"]] = bad
            if not r["runtime_eligibility_matches"]:
                harness["eligibility_mismatch"].append(r["block"])
            if not pilot and r["eligible"] and not r.get("forked"):
                harness["eligibility_mismatch"].append(f"{r['block']} (eligible, not forked)")
            if not pilot and not r["eligible"] and r.get("forked"):
                harness["eligibility_mismatch"].append(f"{r['block']} (complete, but forked)")
        counts = sampling_counts(records)
        outcomes = {o: sum(1 for r in records if r.get("eligible") and r.get("outcome") == o)
                    for o in ("T_only", "C_only", "Both", "Neither")}
        transitions = {}
        for r in records:
            if "outcome" not in r:
                continue
            for arm in ARMS:
                for rev in ("base", "head"):
                    key = (f"{arm}:{r['initial']['revisions'][rev]['class']}->"
                           f"{r['finals'][arm]['revisions'][rev]['class']}")
                    transitions[key] = transitions.get(key, 0) + 1
        per_fixture[fixture] = {**counts, "outcomes": outcomes, "transitions": transitions,
                                "reached_target": done(fixture, counts, pilot),
                                "opportunity_met": pilot or fixture in SANITY
                                or counts["complete_pairs"] >= K_ELIGIBLE}
    harness["frozen_verifier_rows_intact"] = S.frozen_ok()
    harness_ok = not any(harness[k] for k in ("context_leak", "foreign_tools", "harness_errors",
                                               "isolation", "locked_hop_rejected",
                                               "eligibility_mismatch")) \
        and harness["frozen_verifier_rows_intact"]
    status, criteria, pooled = decide(harness_ok, pilot, per_fixture, bool(config_mismatch))
    return {"protocol": PROTOCOL, "pilot": pilot, "status": status,
            "targets": {"K_eligible_pairs": K_ELIGIBLE, "M_initials": M_INITIALS,
                        "N_sanity": N_SANITY},
            "pooled": pooled, "criteria": criteria,
            "per_fixture": per_fixture, "harness": harness, "harness_ok": harness_ok,
            "config_mismatch": config_mismatch,
            "blocks": all_records}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = score(args.pilot)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, default=list) + "\n")
    print(json.dumps({k: result.get(k) for k in ("status", "pooled", "criteria", "harness_ok",
                                                 "problems")}, indent=1, default=list))
    for f, v in result.get("per_fixture", {}).items():
        print(f, {k: v[k] for k in ("valid_initials", "initially_full", "eligible",
                                    "complete_pairs", "outcomes")})


if __name__ == "__main__":
    main()
