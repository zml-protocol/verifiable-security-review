"""RD verifier conformance (PREREGISTRATION.md §15.1 item 3; §15.10 step 2, the last gate).

    uv run python experiments/rd/conformance.py run      # attempt 1; attempt 2 only after a tool failure
    uv run python experiments/rd/conformance.py score    # results/rd-conformance.json, rd-vocabulary.json

Do the frozen verifiers agree with the admissible relation definitions? The synthetic relation
cases (experiments/rd/boundary/relation_cases.yaml, every one admissible in round 1) are judged by
the frozen verifiers through the frozen §14 machinery (bridge.analyze: P-Hybrid-1 queries plus the
bridge queries; bridge.judge: anchor -> shape -> relation), and compared with the admissible labels.
No query is changed for this check, before or after it.

Unit: one verifier implementation, codeql/<language>/<relation>; a per-relation rollup is report
only. Per case: TRUE->VERIFIED a supported hit; TRUE->UNVERIFIED a provider blind spot, not a
disagreement; FALSE->VERIFIED or TRUE->CONTRADICTED a disagreement with the definition. Per verifier
(the frozen score_states classes):
- UNSAFE -> NON_CONFORMANT: §15.1.3, this verifier leaves the RD provider vocabulary (per language:
  another language's verifier of the same relation is unaffected); its verdicts are never VERIFIED
  evidence; the relation keeps its definition in the truth vocabulary;
- BLIND -> UNSUPPORTED: the provider cannot verify this relation in this language; the relation
  keeps its definition;
- PARTIAL, SUPPORTED -> provider support, with its blind spots listed;
- INCONCLUSIVE_TOOL_FAILURE -> no conformance result.

Attempts: attempt 1 is kept for good. Attempt 2 is allowed only when attempt 1 had a tool failure,
reruns only the fixtures that failed, and never overwrites attempt 1; there is no attempt 3. A
result without a tool failure is never rerun. Attempt 2 must run on the very harness attempt 1 ran
on: the same harness commit, CodeQL tag and query/harness file hashes, or it is refused (an
infrastructure retry never changes the instrument; a harness bug means a new protocol version).
So nothing is committed between the two attempts.

Integrity (expected-set driven): the required verifiers are the admissible relation groups of the
frozen truth vocabulary; every one must appear, with at least one admissible TRUE and one FALSE
case, every case must belong to exactly one of them, and no other verifier may appear. Otherwise
PROTOCOL_INVALID, and no tables are written.

Gate (results/rd-vocabulary.json): READY, INCONCLUSIVE_TOOL_FAILURE or PROTOCOL_INVALID. Candidate
selection may read the OSV snapshot only when gate_ready() is true.

B phase (fixed here, applied by the agent protocol): SUPPORTED and PARTIAL verifiers make hops of
their relation-language pair machine-verifiable; for UNSUPPORTED and NON_CONFORMANT pairs an agent
may still state the relation, but the system only ever marks it unsupported / unverified, never
VERIFIED. Agents learn only whether a pair is verifiable, not the synthetic blind spots.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = ROOT / "results"
RUNS = ROOT / "runs" / "rd" / "conformance"
BOUNDARY = HERE / "boundary"
sys.path.insert(0, str(ROOT / "experiments" / "hop_bridge"))
sys.path.insert(0, str(BOUNDARY))

import bridge  # frozen §14: analyze, judge, scored, relations
import check as C

SET = "rd-conformance"
MAX_ATTEMPTS = 2
VOCABULARY = RESULTS / "rd-vocabulary.json"
PROVIDER_STATUS = {"UNSAFE": "NON_CONFORMANT", "INCONCLUSIVE_TOOL_FAILURE": "TOOL_FAILURE",
                   "BLIND": "UNSUPPORTED", "PARTIAL": "PARTIAL", "SUPPORTED": "SUPPORTED"}
B_PHASE = ("SUPPORTED and PARTIAL verifiers make hops of their relation-language pair machine-"
           "verifiable. For UNSUPPORTED and NON_CONFORMANT pairs an agent may still state the relation, "
           "but the system only ever marks it unsupported / unverified, never VERIFIED. Agents learn "
           "only whether a pair is verifiable, not the synthetic blind spots.")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def harness_commit() -> tuple[str, bool]:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return git("rev-parse", "HEAD").strip(), bool(git("status", "--porcelain").strip())


def query_files() -> list[Path]:
    return sorted([*(ROOT / "experiments" / "hop_verify" / "queries").rglob("*.ql*"),
                   *(ROOT / "experiments" / "hop_bridge" / "queries").rglob("*.ql*")])


# ---- attempts ---------------------------------------------------------------------------------


def attempt_path(n: int) -> Path:
    return RUNS / f"attempt-{n}" / "states.json"


def failed_fixtures(attempt: dict) -> list[str]:
    """Fixtures whose analysis failed or produced a TOOL_FAILURE verdict."""
    bad = {fid for fid, status in attempt["provenance"]["analysis_status"].items() if status != "ok"}
    bad |= {s["fixture"] for s in attempt["states"].values() if s["state"] == "TOOL_FAILURE"}
    return sorted(bad)


def plan(attempts: list[dict]) -> tuple[int, list[str] | None, str]:
    """(attempt number, fixtures to run (None: all), refusal reason or "")."""
    if not attempts:
        return 1, None, ""
    if len(attempts) >= MAX_ATTEMPTS:
        return 0, [], f"{MAX_ATTEMPTS} attempts made; there is no attempt {MAX_ATTEMPTS + 1}"
    failed = failed_fixtures(attempts[-1])
    if not failed:
        return 0, [], "attempt 1 had no tool failure; a result is never rerun"
    return len(attempts) + 1, failed, ""


def merged(attempts: list[dict]) -> dict:
    """The verdicts in force: each fixture's from the last attempt that ran it."""
    states = {}
    for a in attempts:
        ran = set(a["provenance"]["fixtures_run"])
        states = {k: v for k, v in states.items() if v["fixture"] not in ran} | a["states"]
    return states


def load_attempts() -> list[dict]:
    return [json.loads(attempt_path(n).read_text()) for n in range(1, MAX_ATTEMPTS + 1)
            if attempt_path(n).exists()]


RETRY_REFUSED = "frozen conformance implementation changed; infrastructure retry is not permitted"


def instrument_files() -> list[Path]:
    return [BOUNDARY / "relation_cases.yaml", HERE / "conformance.py",
            ROOT / "experiments" / "hop_bridge" / "bridge.py", *query_files()]


def instrument(commit: str) -> dict:
    """What an attempt runs on: the harness commit, the CodeQL tag and every instrument file's hash."""
    return {"commit": commit, "codeql": bridge.verify.reach.CODEQL_TAG,
            "files": {str(p.relative_to(ROOT)): sha256(p) for p in instrument_files()}}


def retry_problems(first: dict, now: dict) -> list[str]:
    """Attempt 2 must run on attempt 1's instrument, field by field (a matching commit field does
    not excuse a changed file)."""
    out = []
    if first["harness"]["commit"] != now["commit"]:
        out.append(f"harness commit {now['commit'][:12]} != attempt 1's {first['harness']['commit'][:12]}")
    if first["codeql"] != now["codeql"]:
        out.append(f"CodeQL {now['codeql']} != attempt 1's {first['codeql']}")
    if first["files"] != now["files"]:
        changed = sorted(set(first["files"]) ^ set(now["files"])
                         | {f for f in set(first["files"]) & set(now["files"]) if first["files"][f] != now["files"][f]})
        out.append(f"instrument files differ: {changed}")
    return out


def run(_args: argparse.Namespace) -> None:
    commit, dirty = harness_commit()
    if dirty:
        sys.exit("working tree is dirty; the conformance run starts from the frozen commit only")
    attempts = load_attempts()
    n, only, refusal = plan(attempts)
    if refusal:
        sys.exit(refusal)
    now = instrument(commit)
    if n > 1 and (problems := retry_problems(attempts[0]["provenance"], now)):
        sys.exit(RETRY_REFUSED + ": " + "; ".join(problems))
    cases = C.load("relation_cases.yaml")
    if C.leaks(cases):
        sys.exit("label fields in the case file")
    fixtures = {fid: f for fid, f in cases["fixtures"].items() if only is None or fid in only}
    analyses = {}
    for fid, fixture in fixtures.items():
        print(f"[{SET} attempt {n}] {fid}", flush=True)
        analyses[fid] = bridge.analyze(SET, fid, fixture, "base")
    states = {h["id"]: {"relation": h["relation"], "fixture": h["fixture"], "revision": h["revision"],
                        **bridge.judge(h, cases["fixtures"][h["fixture"]], analyses[h["fixture"]])}
              for h in cases["hops"] if h["fixture"] in fixtures}
    out = attempt_path(n)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"set": SET, "attempt": n, "provenance": {
        "harness": {"commit": commit, "dirty": dirty}, "codeql": now["codeql"],
        "fixtures_run": sorted(fixtures),
        "analysis_status": {fid: a["status"] for fid, a in analyses.items()},
        "files": now["files"]}, "states": states}, indent=2))
    print({k: sum(v["state"] == k for v in states.values()) for k in bridge.STATES})


# ---- score and gate ---------------------------------------------------------------------------


def provider_table(verifiers: dict) -> dict:
    out = {}
    for key, m in sorted(verifiers.items()):
        hops = m["hops"]
        out[key] = {
            "true_verified": m["true_verified"], "true_unverified": m["true_unverified"],
            "true_contradicted": m["true_contradicted"], "false_verified": m["false_verified"],
            "false_unverified": m["false_unverified"], "false_contradicted": m["false_contradicted"],
            "caught_by_anchor": m["caught_by_anchor"], "tool_failures": m["tool_failures"],
            "class": m["class"], "status": PROVIDER_STATUS[m["class"]],
            "blind_spots": sorted(h["name"] for h in hops.values() if h["label"] and h["state"] == "UNVERIFIED"),
            "disagreements": sorted(h["name"] for h in hops.values()
                                    if (not h["label"] and h["state"] == "VERIFIED")
                                    or (h["label"] and h["state"] == "CONTRADICTED")),
        }
    return out


def truth_vocabulary() -> dict:
    """From the decidability rounds: a group's final outcome is its last round's."""
    final = {}
    for n in (1, 2):
        path = RESULTS / f"rd-boundary-r{n}-decision.json"
        decision = json.loads(path.read_text())
        if decision["status"] != "SCORED":
            sys.exit(f"{path.name} is not scored")
        for group, g in decision["groups"].items():
            final[group] = {"round": n, "outcome": g["outcome_without_revision"],
                            "indeterminate_rules": g["indeterminate_rules"]}
    return dict(sorted(final.items()))


def required_verifiers(tv: dict) -> list[str]:
    """Expected set: every admissible relation group (language/relation) of the truth vocabulary."""
    return sorted(f"codeql/{g}" for g, v in tv.items() if "/" in g and v["outcome"] == "ADMISSIBLE")


def verifier_of(hop: dict, cases: dict) -> str:
    return bridge.verifier_key(cases["fixtures"][hop["fixture"]]["language"], hop["relation"])


def integrity_problems(required: list[str], cases: dict, labels: dict, provider_keys: list[str],
                       states: dict) -> list[str]:
    problems = []
    if set(provider_keys) != set(required):
        problems.append(f"verifiers in the table {sorted(provider_keys)} != required {required}")
    seen: dict[str, set] = {k: set() for k in required}
    for h in cases["hops"]:
        key = verifier_of(h, cases)
        if key not in seen:
            problems.append(f"{h['id']}: belongs to no required verifier ({key})")
            continue
        seen[key].add(labels[h["id"]]["label"])
    for key, values in seen.items():
        for value in (True, False):
            if value not in values:
                problems.append(f"{key}: no admissible {'TRUE' if value else 'FALSE'} case")
    if set(states) != {h["id"] for h in cases["hops"]}:
        problems.append("the verdicts in force do not cover exactly the cases")
    return problems


def gate(problems: list[str], provider: dict) -> str:
    if problems:
        return "PROTOCOL_INVALID"
    if any(v["status"] == "TOOL_FAILURE" for v in provider.values()):
        return "INCONCLUSIVE_TOOL_FAILURE"
    return "READY"


def score(_args: argparse.Namespace) -> None:
    attempts = load_attempts()
    if not attempts:
        sys.exit("no attempt has run")
    states = merged(attempts)
    cases = C.load("relation_cases.yaml")
    labels = C.load("relation_labels.yaml")["labels"]
    tv = truth_vocabulary()
    required = required_verifiers(tv)
    # `kind` groups the false cases in the frozen scorer: here, by the rule each case tests
    truth = {cid: {"label": v["label"], "name": v["name"], "kind": v["rule"]} for cid, v in labels.items()}
    problems = [] if set(truth) == set(states) else ["verdicts and labels cover different cases"]
    provider = {}
    if not problems:
        scored = bridge.scored(states, cases, truth)
        provider = provider_table(scored["verifiers"])
    problems += integrity_problems(required, cases, labels, list(provider), states)
    status = gate(problems, provider)
    provenance = {"attempts": [{"attempt": a["attempt"], **a["provenance"]} for a in attempts],
                  "labels": {"experiments/rd/boundary/relation_labels.yaml": sha256(BOUNDARY / "relation_labels.yaml")}}
    if status == "PROTOCOL_INVALID":
        doc = {"gate_status": status, "problems": problems, "provenance": provenance}
        VOCABULARY.write_text(json.dumps(doc, indent=2) + "\n")
        (RESULTS / "rd-conformance.json").write_text(json.dumps(doc, indent=2) + "\n")
        print(status, *problems, sep="\n")
        sys.exit(1)
    (RESULTS / "rd-conformance.json").write_text(json.dumps({
        "set": SET, "gate_status": status, "required_verifiers": required, "provenance": provenance,
        "provider_support": provider, "false_cases_by_rule": scored["false_hops_by_mutation"],
        "report_only_by_relation": scored["report_only_by_relation"]}, indent=2) + "\n")
    VOCABULARY.write_text(json.dumps({
        "gate_status": status, "truth_vocabulary": tv,
        "provider_support": {k: {"status": v["status"], "blind_spots": v["blind_spots"],
                                 "disagreements": v["disagreements"]} for k, v in provider.items()},
        "b_phase": B_PHASE, "coverage_note": "synthetic boundary coverage is limited (1-5 cases per side)",
    }, indent=2) + "\n")
    print("gate:", status)
    for k, v in provider.items():
        total = v["true_verified"] + v["true_unverified"] + v["true_contradicted"]
        print(f"{k:34} {v['status']:15} true {v['true_verified']}/{total}  false verified {v['false_verified']}")


def gate_ready() -> bool:
    """For candidate selection: the OSV snapshot may be read only when this is true."""
    if not VOCABULARY.exists():
        return False
    return json.loads(VOCABULARY.read_text()).get("gate_status") == "READY"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("score")
    args = ap.parse_args()
    {"run": run, "score": score}[args.cmd](args)


if __name__ == "__main__":
    main()
