"""P-Hybrid-2 scoring (PREREGISTRATION.md §11.5-11.7). Deterministic: the frozen matcher,
the frozen verifier rows, and the blind review labels once they exist.

    uv run python experiments/hop_propose/propose_score.py --out results/p-hybrid-2-scores.json
    uv run python experiments/hop_propose/propose_score.py --pilot --out runs/hop_propose/pilot-scores.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import propose_run as R

from spike import hops as hoplib

ARMS = R.ARMS
MIN_PAIRS_PER_FIXTURE = 4
THRESHOLDS = {"mean_gain": 0.15, "max_pairs_treatment_below": 2, "false_share_margin": 0.10}
CADDY = "caddy-forward-auth"
LABELS = ("TRUE", "FALSE", "INDETERMINATE")
REVIEW = {"primary": ROOT / "results" / "p-hybrid-2-review-primary.yaml",
          "secondary": ROOT / "results" / "p-hybrid-2-review-secondary.yaml"}


def rate(num: float, den: float) -> float:
    """§11.5: every rate with an empty denominator is 0 (nothing was claimed)."""
    return num / den if den else 0.0


# ---- golden hops and matching ----------------------------------------------------------


def golden_hops(fixture: str, pilot: bool) -> list[dict]:
    """The frozen §10 true hops of this fixture, canonical, with their P-Hybrid-1 ids."""
    entry, _ = R.case_of(fixture, pilot)
    base = ROOT / "experiments" / "hop_verify"
    hop_set = yaml.safe_load((base / "sets" / f"{entry['golden_set']}.yaml").read_text())
    truth = yaml.safe_load((base / "truth" / f"{entry['golden_set']}.yaml").read_text())["truth"]
    return [{"id": h["id"], **{k: h[k] for k in ("revision", "relation", "from", "to")}}
            for h in hop_set["hops"] if h["fixture"] == fixture and truth[h["id"]]["label"]]


class Matcher:
    """Resolves hops of one fixture against the frozen analyses and the golden hops."""

    def __init__(self, fixture: str, pilot: bool):
        self.fixture = fixture
        self.entry, case = R.case_of(fixture, pilot)
        self.text_of = R.text_reader(case)
        self.analysis = {rev: R.load_analysis(fixture, rev) for rev in ("base", "head")}
        self.golden = golden_hops(fixture, pilot)
        self.golden_resolved = {g["id"]: self.resolve(g) for g in self.golden}

    def resolve(self, hop: dict) -> hoplib.Resolved:
        return hoplib.resolve(hop, self.text_of, R.RELATIONS, self.analysis[hop["revision"]],
                              self.entry["language"])

    def identity(self, hop: dict, res: hoplib.Resolved) -> tuple:
        """Blind-review unit: the nodes a hop names (anchors for an unsupported relation)."""
        ends = []
        for side, node, at in (("from", res.node_from, res.anchor_from),
                               ("to", res.node_to, res.anchor_to)):
            ends.append(list(node) if node else ["anchor", hop[side]["file"], *at])
        return (self.fixture, hop["revision"], hop["relation"], *map(tuple, ends))

    def submission(self, hops: list[dict] | None) -> dict:
        hops = hops or []
        rows, verified_golden, located_golden = [], set(), set()
        for hop in hops:
            canonical = {k: hop[k] for k in ("revision", "relation", "from", "to")}
            try:
                res = self.resolve(canonical)
            except hoplib.HopError as e:
                # validated at submit with the same frozen rows: a rejection here means the
                # runtime and the scorer disagree, a harness invariant violation (§11.7)
                rows.append({"id": hop["id"], "relation": hop["relation"], "state": "REJECTED",
                             "problem": f"[{e.code}] {e}", "golden": [], "located": [], "unit": None})
                continue
            state = hoplib.verdict(canonical, res, R.RELATIONS, self.analysis[hop["revision"]])
            typed, located = [], []
            for g in self.golden:
                gres = self.golden_resolved[g["id"]]
                a = self.analysis[g["revision"]]
                if hoplib.located(canonical, res, g, gres, R.RELATIONS, a):
                    located.append(g["id"])
                    if hoplib.matches(canonical, res, g, gres, R.RELATIONS, a):
                        typed.append(g["id"])
            located_golden.update(located)
            if state == "VERIFIED":
                verified_golden.update(typed)
            rows.append({"id": hop["id"], "relation": hop["relation"], "state": state,
                         "golden": typed, "located": located,
                         "unit": None if typed else json.dumps(self.identity(canonical, res))})
        n_golden = len(self.golden)
        supported = [r for r in rows if r["relation"] != hoplib.UNSUPPORTED]
        return {
            "hops": rows,
            "n": len(rows),
            "verified": sum(r["state"] == "VERIFIED" for r in rows),
            "contradicted": sum(r["state"] in ("CONTRADICTED", "REJECTED") for r in rows),
            "rejected": [r["id"] for r in rows if r["state"] == "REJECTED"],
            "supported": len(supported),
            "unsupported": len(rows) - len(supported),
            "verified_golden": sorted(verified_golden),
            "located_golden": sorted(located_golden),
            "verified_coverage": rate(len(verified_golden), n_golden),
            "located_coverage": rate(len(located_golden), n_golden),
        }


# ---- runs, validity and invariants ---------------------------------------------------


def blocks(pilot: bool) -> list[tuple[str, int]]:
    if pilot:
        return [(f, 0) for f in sorted(R.CASES["pilot"])]
    return R.read_order(HERE / "order.txt")


def state_of(run_dir: Path) -> dict | None:
    path = run_dir / "state.json"
    return json.loads(path.read_text()) if path.exists() else None


def leaks(run_dir: Path, block_dir: Path) -> list[str]:
    """§11.6 context-leak invariant, as in §8: the cwd, auto-memory, and the arm, block or
    run directory being visible to the agent."""
    found = []
    env = json.loads((run_dir / "meta.json").read_text()).get("agent_environment", {})
    cwd = env.get("cwd") or ""
    if cwd and Path(cwd).resolve().is_relative_to(ROOT):
        found.append("cwd_inside_repo")
    if env.get("memory_files"):
        found.append("auto_memory")
    init = next((e for e in R.agent_events(run_dir)
                 if e.get("type") == "system" and e.get("subtype") == "init"), {})
    init_text = json.dumps(init)
    for token in (*ARMS, str(block_dir), str(ROOT)):
        if token in init_text:
            found.append(f"init_shows:{token.rsplit('/', 1)[-1]}")
    transcript = run_dir / "transcript.jsonl"
    if transcript.exists():
        text = transcript.read_text()
        for token in (str(block_dir), str(ROOT)):
            if token in text:
                found.append("tool_result_shows_path")
    return found


def foreign_tools(run_dir: Path) -> list[str]:
    names = set()
    for e in R.agent_events(run_dir):
        if e.get("type") == "assistant":
            for c in e["message"].get("content", []):
                if c.get("type") == "tool_use" and not c["name"].startswith("mcp__secreview__"):
                    names.add(c["name"])
    return sorted(names)


def harness_errors(run_dir: Path) -> int:
    path = run_dir / "transcript.jsonl"
    if not path.exists():
        return 0
    return sum('"internal_error"' in line for line in path.read_text().splitlines())


def isolation_problems(block_dir: Path) -> list[str]:
    iso = json.loads((block_dir / "isolation.json").read_text())
    out = []
    if iso["parent_session_sha256_before"] is None:
        out.append("parent_session_file_missing")
    elif iso["parent_session_sha256_before"] != iso["parent_session_sha256_after"]:
        out.append("parent_session_changed")
    snapshot = json.loads((block_dir / "initial" / "snapshot.json").read_text())["initial"]
    served = {json.loads((block_dir / "initial" / "meta.json").read_text())["served_session"]}
    for arm in ARMS:
        child = iso["children"].get(arm)
        if not child:
            out.append(f"{arm}_missing")
            continue
        if child["initial_state_sha256"] != iso["snapshot_sha256"]:
            out.append(f"{arm}_snapshot_differs")
        state = state_of(block_dir / arm)
        if state is None or state["initial"] != snapshot:
            out.append(f"{arm}_initial_differs")
        if child["served_session"] in served or child["served_session"] is None:
            out.append(f"{arm}_session_not_forked")
        served.add(child["served_session"])
    return out


def frozen_ok() -> bool:
    import gzip

    manifest = json.loads((R.FROZEN / "manifest.json").read_text())["files"]
    return all(hashlib.sha256(gzip.decompress((R.FROZEN / name).read_bytes())).hexdigest()
               == entry["sha256_json"] for name, entry in manifest.items())


# ---- review labels ------------------------------------------------------------------------


REVIEWER_TYPES = ("human", "model")
ATTESTATION = {"independent": True, "saw_arms": False, "saw_verdicts": False}


def reviewer_of(doc: dict) -> dict | None:
    """§11.6: a label file names its reviewer and carries the blindness attestation. The
    scorer cannot check the statement, only that it was made."""
    reviewer = doc.get("reviewer") if isinstance(doc, dict) else None
    if not isinstance(reviewer, dict) or reviewer.get("type") not in REVIEWER_TYPES:
        return None
    if not str(reviewer.get("name") or "").strip():
        return None
    attest = reviewer.get("attestation")
    if not isinstance(attest, dict) or any(attest.get(k) is not v for k, v in ATTESTATION.items()):
        return None
    return reviewer


def load_review(which: str, pilot: bool) -> dict | None:
    """{"reviewer": ..., "labels": unit key -> label}, or None until a complete, attested
    label file exists."""
    path = REVIEW[which]
    if pilot or not path.exists():
        return None
    units = json.loads((R.runs_root(pilot) / "review" / "units.json").read_text())
    doc = yaml.safe_load(path.read_text())
    reviewer = reviewer_of(doc)
    if reviewer is None:
        return None  # no reviewer identity or attestation: not a usable review
    raw = doc.get("labels") or {}
    if set(raw) != set(units):
        return None
    labels = {}
    for rid, value in raw.items():
        label = value["label"] if isinstance(value, dict) else value
        if label not in LABELS:
            return None  # incomplete or malformed: treated as not yet reviewed
        labels[units[rid]["key"]] = label
    return {"reviewer": reviewer, "labels": labels}


def validity_share(arm_rows: list[dict], labels: dict[str, str]) -> dict:
    counts = dict.fromkeys(LABELS, 0)
    missing = 0
    for row in arm_rows:
        if row["unit"] is None:
            continue
        label = labels.get(row["unit"])
        if label is None:
            missing += 1
        else:
            counts[label] += 1
    return {**counts, "missing": missing,
            "false_share": rate(counts["FALSE"], counts["TRUE"] + counts["FALSE"])}


# ---- main -------------------------------------------------------------------------------


def score(pilot: bool) -> dict:
    root = R.runs_root(pilot)
    matchers: dict[str, Matcher] = {}
    pairs, incomplete, invariants = [], [], {"isolation": {}, "context_leak": {},
                                               "foreign_tools": {}, "harness_errors": 0,
                                               "locked_hop_rejected": {}}
    for fixture, repeat in blocks(pilot):
        block = root / fixture / f"r{repeat}"
        name = f"{fixture}/r{repeat}"
        dirs = {"initial": block / "initial", **{arm: block / arm for arm in ARMS}}
        validity = {k: (R.classify(d) if (d / "meta.json").exists() else ("MISSING", "not_run"))
                    for k, d in dirs.items()}
        if any(v[0] != "VALID" for v in validity.values()):
            incomplete.append({"block": name, "validity": validity})
            continue
        for k, d in dirs.items():
            if found := leaks(d, block):
                invariants["context_leak"][f"{name}/{k}"] = found
            if tools := foreign_tools(d):
                invariants["foreign_tools"][f"{name}/{k}"] = tools
            invariants["harness_errors"] += harness_errors(d)
        if problems := isolation_problems(block):
            invariants["isolation"][name] = problems
        m = matchers.setdefault(fixture, Matcher(fixture, pilot))
        initial = m.submission(state_of(dirs["initial"])["initial"])
        finals = {arm: m.submission(state_of(dirs[arm])["final"]) for arm in ARMS}
        for phase, sub in (("initial", initial), *finals.items()):
            if sub["rejected"]:
                invariants["locked_hop_rejected"][f"{name}/{phase}"] = sub["rejected"]
        pairs.append({
            "block": name, "fixture": fixture, "repeat": repeat, "validity": validity,
            "initial": initial, **finals,
            "gain": finals["treatment"]["verified_coverage"] - finals["control"]["verified_coverage"],
            "costs": {k: json.loads((d / "meta.json").read_text()).get("cost_usd")
                      for k, d in dirs.items()},
        })
    return summarize(pairs, incomplete, invariants, pilot)


def summarize(pairs: list[dict], incomplete: list[dict], invariants: dict, pilot: bool) -> dict:
    fixtures = sorted(R.CASES["pilot" if pilot else "eval"])
    per_fixture = {f: sum(p["fixture"] == f for p in pairs) for f in fixtures}
    harness = {"isolation": invariants["isolation"], "context_leak": invariants["context_leak"],
               "foreign_tools": invariants["foreign_tools"],
               "harness_errors": invariants["harness_errors"],
               "locked_hop_rejected": invariants.get("locked_hop_rejected", {}),
               "frozen_analysis_intact": frozen_ok()}
    harness_ok = not (harness["isolation"] or harness["context_leak"] or harness["foreign_tools"]
                      or harness["harness_errors"] or harness["locked_hop_rejected"]
                      ) and harness["frozen_analysis_intact"]

    def pooled(phase: str) -> dict:
        subs = [p[phase] for p in pairs]
        n, supported = sum(s["n"] for s in subs), sum(s["supported"] for s in subs)
        return {
            "verified_coverage": rate(sum(s["verified_coverage"] for s in subs), len(subs)),
            "located_coverage": rate(sum(s["located_coverage"] for s in subs), len(subs)),
            "hops": n,
            "proposal_verification_rate": rate(sum(s["verified"] for s in subs), n),
            "contradiction_rate": rate(sum(s["contradicted"] for s in subs), supported),
            "unsupported": sum(s["unsupported"] for s in subs),
            "unsupported_share": rate(sum(s["unsupported"] for s in subs), n),
        }

    phases = {phase: pooled(phase) for phase in ("initial", *ARMS)}
    gains = [p["gain"] for p in pairs]
    caddy = [p for p in pairs if p["fixture"] == CADDY]
    caddy_detail = [{
        "block": p["block"], "control": p["control"]["verified_golden"],
        "treatment": p["treatment"]["verified_golden"],
        "treatment_only_from_uncovered_initial": sorted(
            set(p["treatment"]["verified_golden"]) - set(p["initial"]["verified_golden"])
            - set(p["control"]["verified_golden"])),
    } for p in caddy]

    loaded = {which: load_review(which, pilot) for which in REVIEW}
    reviewers = {w: r and r["reviewer"] for w, r in loaded.items()}
    reviews = {w: r and r["labels"] for w, r in loaded.items()}
    validity = None
    if reviews["primary"] is not None:
        validity = {arm: validity_share([h for p in pairs for h in p[arm]["hops"]],
                                        reviews["primary"]) for arm in ("initial", *ARMS)}
    agreement = None
    if reviews["primary"] is not None and reviews["secondary"] is not None:
        both = set(reviews["primary"]) & set(reviews["secondary"])
        agreement = {"units": len(both), "agree": sum(reviews["primary"][k] == reviews["secondary"][k]
                                                     for k in both)}

    criteria = {
        "mean_gain": rate(sum(gains), len(gains)) >= THRESHOLDS["mean_gain"],
        "few_pairs_treatment_below": sum(g < 0 for g in gains)
        <= THRESHOLDS["max_pairs_treatment_below"],
        "false_share_guard": None if validity is None else (
            validity["treatment"]["false_share"]
            <= validity["control"]["false_share"] + THRESHOLDS["false_share_margin"]),
        "caddy_pair_treatment_above": any(p["gain"] > 0 for p in caddy),
    }
    thin = {f: n for f, n in per_fixture.items() if n < MIN_PAIRS_PER_FIXTURE}
    missing_labels = validity is not None and any(v["missing"] for v in validity.values())
    if thin:
        verdict = "INCONCLUSIVE_INFRA"
    elif not harness_ok:
        verdict = "HARNESS_INVALID"
    elif validity is None or missing_labels:
        verdict = "REVIEW_PENDING"
    else:
        verdict = "SUCCESS" if all(criteria.values()) else "FAIL"
    return {
        "protocol": R.PROTOCOL, "pilot": pilot, "verdict": verdict,
        "thresholds": THRESHOLDS, "criteria": criteria,
        "pairs_per_fixture": per_fixture, "fixtures_below_minimum": thin,
        "mean_gain": rate(sum(gains), len(gains)),
        "pairs_treatment_below": sum(g < 0 for g in gains),
        "pairs_treatment_above": sum(g > 0 for g in gains),
        "phases": phases,
        "per_fixture": {f: {phase: rate(sum(p[phase]["verified_coverage"] for p in pairs
                                            if p["fixture"] == f), per_fixture[f])
                            for phase in ("initial", *ARMS)} for f in fixtures},
        "caddy": caddy_detail,
        "novel_hop_validity": validity, "review_agreement": agreement,
        "reviewers": reviewers,
        "primary_review_kind": None if reviewers["primary"] is None else (
            "human" if reviewers["primary"]["type"] == "human" else "model-blind adjudication"),
        "harness": harness, "harness_ok": harness_ok,
        "incomplete_blocks": incomplete, "pairs": pairs,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = score(args.pilot)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    brief = {k: result[k] for k in ("verdict", "criteria", "pairs_per_fixture", "mean_gain",
                                    "pairs_treatment_below", "harness_ok")}
    print(json.dumps(brief, indent=2))
    print(json.dumps(result["phases"], indent=2))


if __name__ == "__main__":
    main()
