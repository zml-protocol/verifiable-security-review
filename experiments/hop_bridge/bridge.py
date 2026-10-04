"""§14 P-extension: bridge verifiers from the long-frozen Spike P source endpoints to the §12
local subgraph (PREREGISTRATION.md §14). Provider-only: no LLM.

    uv run python experiments/hop_bridge/bridge.py check --set dev|cal|current
    uv run python experiments/hop_bridge/bridge.py run --set dev|cal|current
    uv run python experiments/hop_bridge/bridge.py score --set dev|cal|current
    uv run python experiments/hop_bridge/bridge.py chain        # current fixtures: entry -> terminal
    uv run python experiments/hop_bridge/bridge.py decide

Relations are the frozen P-Hybrid-1 ones plus the bridge ones (relations.yaml), resolved and
judged by the shared hop core (spike.hops). `run` never reads truth/.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for sub in ("hop_verify", "hop_chain"):
    sys.path.insert(0, str(ROOT / "experiments" / sub))

import chain  # §12 chain classifier, frozen
import connector as C  # §12.1 same-object connector, frozen
import verify  # P-Hybrid-1: analyze, run_query, source, score_states

from spike import hops as hoplib

RUNS = ROOT / "runs" / "hop_bridge"
RESULTS = ROOT / "results"
SETS = ("dev", "cal", "current")
HELD_OUT = ("cal", "current")
BRIDGE = yaml.safe_load((HERE / "relations.yaml").read_text())
P1 = verify.relations()["relations"]
FROZEN_P1 = ROOT / "experiments" / "hop_propose" / "frozen"
CURRENT_DBS = ROOT / "runs" / "hop_propose" / "analysis"
STATES = ("VERIFIED", "UNVERIFIED", "CONTRADICTED", "ANCHOR_REJECTED", "TOOL_FAILURE")


def relations(language: str) -> dict:
    """P-Hybrid-1 relations of the language plus the bridge ones, in the spike.hops format."""
    out = {n: r for n, r in P1.items() if r["language"] == language}
    out |= {n: {**r, "language": language} for n, r in BRIDGE["relations"][language].items()}
    return out


def bridge_names(language: str) -> set[str]:
    return set(BRIDGE["relations"][language])


def hop_set(name: str) -> dict:
    return yaml.safe_load((HERE / "sets" / f"{name}.yaml").read_text())


def truth_of(name: str) -> dict:
    return yaml.safe_load((HERE / "truth" / f"{name}.yaml").read_text())


def text_reader(fixture: dict):
    return lambda rev, file: verify.source(fixture, rev, file)


# ---- check ------------------------------------------------------------------------------


def check_set(name: str) -> list[str]:
    s, t = hop_set(name), truth_of(name)["truth"]
    problems, seen = [], {}
    for hop in s["hops"]:
        hid = hop.get("id")
        if set(hop) != {"id", "fixture", "revision", "relation", "from", "to"}:
            problems.append(f"{hid}: keys (hops carry no truth)")
            continue
        fixture = s["fixtures"].get(hop["fixture"])
        if fixture is None or hop["revision"] not in fixture["commits"]:
            problems.append(f"{hid}: unknown fixture or revision")
            continue
        rels = relations(fixture["language"])
        if hop["relation"] not in rels:
            problems.append(f"{hid}: relation {hop['relation']} not for {fixture['language']}")
            continue
        key = json.dumps([hop[k] for k in ("fixture", "revision", "relation", "from", "to")],
                         sort_keys=True)
        if key in seen:
            problems.append(f"{hid}: duplicate of {seen[key]}")
        seen[key] = hid
        entry = t.get(hid)
        if entry is None or not isinstance(entry.get("label"), bool):
            problems.append(f"{hid}: no truth label")
            continue
        if entry["label"] is False and not (entry.get("kind") and entry.get("reason")):
            problems.append(f"{hid}: a false hop needs a kind and a reason")
        try:
            for side in ("from", "to"):
                text = verify.source(fixture, hop["revision"], hop[side]["file"])
                if text is None:
                    raise hoplib.HopError("anchor", "file missing")
                hoplib.locate(text, hop[side], fixture["language"] == "go")
            if entry.get("expect") == "anchor_rejected":
                problems.append(f"{hid}: expected the anchor check to reject it, but it anchors")
        except hoplib.HopError as e:
            if entry.get("expect") != "anchor_rejected":
                problems.append(f"{hid}: {e}")
    if extra := set(t) - {h.get("id") for h in s["hops"]}:
        problems.append(f"truth for unknown hops: {sorted(extra)}")
    return problems


def check(args: argparse.Namespace) -> None:
    problems = check_set(args.set)
    for p in problems:
        print(p)
    print(f"{args.set}: {len(hop_set(args.set)['hops'])} hops, {len(problems)} problems")
    sys.exit(1 if problems else 0)


# ---- run --------------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_p1(fid: str, rev: str) -> bytes:
    """The frozen P-Hybrid-1 output of a current fixture, checked against its manifest."""
    name = f"{fid}.{rev}.json.gz"
    data = gzip.decompress((FROZEN_P1 / name).read_bytes())
    manifest = json.loads((FROZEN_P1 / "manifest.json").read_text())["files"]
    if hashlib.sha256(data).hexdigest() != manifest[name]["sha256_json"]:
        sys.exit(f"{name} differs from the frozen manifest")
    return data


def analyze(set_name: str, fid: str, fixture: dict, rev: str) -> dict:
    """Merged analysis: P-Hybrid-1 shapes/rows (frozen for the current fixtures, fresh for the
    synthetic modules) plus the bridge shapes and every bridge verifier of the language."""
    lang = fixture["language"]
    work = RUNS / set_name / fid / rev
    if set_name == "current":
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        db = CURRENT_DBS / fid / rev / "db"
        frozen = json.loads(frozen_p1(fid, rev))
        base = {"status": "ok", "shapes": frozen["shapes"], "rows": frozen["rows"]}
    else:
        base = verify.analyze(fid, fixture, rev, {n for n, r in P1.items() if r["language"] == lang},
                              work)
        if base["status"] != "ok":
            return base
        db = work / "db"
    env = {**os.environ, **(verify.reach.go_env() if lang == "go" else {})}
    queries = HERE / "queries" / lang
    try:
        shapes = verify.run_query(db, queries / BRIDGE["shapes"][lang], work / "bridge_shapes.json", env)
        rows = {n: verify.run_query(db, queries / r["verifier"], work / f"{n}.json", env)
                for n, r in BRIDGE["relations"][lang].items()}
    except RuntimeError as e:
        return {"status": "tool_failure", "stage": "query", "error": str(e)}
    return {"status": "ok", "shapes": base["shapes"] + shapes, "rows": {**base["rows"], **rows}}


def judge(hop: dict, fixture: dict, analysis: dict) -> dict:
    canonical = {k: hop[k] for k in ("revision", "relation", "from", "to")}
    rels = relations(fixture["language"])
    try:
        for side in ("from", "to"):
            text = verify.source(fixture, hop["revision"], hop[side]["file"])
            if text is None:
                raise hoplib.HopError("anchor", "file missing")
            hoplib.locate(text, hop[side], fixture["language"] == "go")
    except hoplib.HopError as e:
        return {"state": "ANCHOR_REJECTED", "detail": str(e)}
    if analysis["status"] != "ok":
        return {"state": "TOOL_FAILURE", "detail": analysis.get("error", "")[:300]}
    try:
        res = hoplib.resolve(canonical, text_reader(fixture), rels, analysis, fixture["language"])
    except hoplib.HopError as e:
        state = {"shape": "CONTRADICTED", "not_analyzed": "TOOL_FAILURE"}.get(e.code, "ANCHOR_REJECTED")
        return {"state": state, "detail": str(e)}
    return {"state": hoplib.verdict(canonical, res, rels, analysis), "detail": ""}


def harness_commit() -> tuple[str, bool]:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return git("rev-parse", "HEAD").strip(), bool(git("status", "--porcelain").strip())


def run(args: argparse.Namespace) -> None:
    """dev reruns freely; cal and current run once, from the frozen commit only, and current only
    after cal passed (§14.8)."""
    commit, dirty = harness_commit()
    if args.set in HELD_OUT:
        if dirty:
            sys.exit("working tree is dirty; cal and current run from the frozen commit only")
        if (RUNS / args.set / "states.json").exists():
            sys.exit(f"{args.set} has already run; it runs once")
    if args.set == "current" and (problems := cal_gate()):
        sys.exit("no current run: " + "; ".join(problems))
    s = hop_set(args.set)
    analyses = {}
    for fid, rev in sorted({(h["fixture"], h["revision"]) for h in s["hops"]}):
        print(f"[{args.set}] {fid} {rev}", flush=True)
        analyses[(fid, rev)] = analyze(args.set, fid, s["fixtures"][fid], rev)
    states = {h["id"]: {"relation": h["relation"], "fixture": h["fixture"], "revision": h["revision"],
                        **judge(h, s["fixtures"][h["fixture"]], analyses[(h["fixture"], h["revision"])])}
              for h in s["hops"]}
    files = [HERE / "relations.yaml", HERE / "bridge.py", HERE / "sets" / f"{args.set}.yaml",
             *sorted((HERE / "queries").rglob("*.ql*"))]
    out = RUNS / args.set / "states.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"set": args.set, "provenance": {
        "harness": {"commit": commit, "dirty": dirty}, "codeql": verify.reach.CODEQL_TAG,
        "files": {str(p.relative_to(ROOT)): _sha256(p) for p in files}}, "states": states}, indent=2))
    print({k: sum(v["state"] == k for v in states.values()) for k in STATES})
    if args.set == "current":
        (RUNS / "current" / "analyses.json").write_text(json.dumps(
            {f"{f}|{r}": a for (f, r), a in analyses.items()}))


# ---- score, chain, decide ------------------------------------------------------------------


PROVIDER = "codeql"


def verifier_key(language: str, relation: str) -> str:
    """§14.5 calibration unit: provider/language/relation names exactly one query file."""
    return f"{PROVIDER}/{language}/{relation}"


def verifier_query(key: str) -> str:
    _, language, relation = key.split("/")
    if relation in BRIDGE["relations"][language]:
        q = HERE / "queries" / language / BRIDGE["relations"][language][relation]["verifier"]
    else:
        q = ROOT / "experiments" / "hop_verify" / "queries" / language / P1[relation]["verifier"]
    return str(q.relative_to(ROOT))


def by_verifier(states: dict, s: dict) -> dict:
    """One class per verifier implementation, so Go and Python `def_use` are scored apart."""
    lang = {fid: f["language"] for fid, f in s["fixtures"].items()}
    return {hid: {**st, "relation": verifier_key(lang[st["fixture"]], st["relation"])}
            for hid, st in states.items()}


def scored(states: dict, s: dict, truth: dict) -> dict:
    """`verifiers` is the only input to `decide`; `report_only_by_relation` merges languages for
    the report and is never routed on."""
    per = verify.score_states(by_verifier(states, s), truth)
    merged = verify.score_states(states, truth)["relations"]
    return {"verifiers": per["relations"],
            "verifier_queries": {k: verifier_query(k) for k in per["relations"]},
            "false_hops_by_mutation": per["false_hops_by_mutation"],
            "report_only_by_relation": {n: {k: v for k, v in m.items() if k != "hops"}
                                        for n, m in merged.items()}}


def score(args: argparse.Namespace) -> None:
    run_out = json.loads((RUNS / args.set / "states.json").read_text())
    truth = truth_of(args.set)["truth"]
    if set(truth) != set(run_out["states"]):
        sys.exit("states and truth cover different hops")
    tf = HERE / "truth" / f"{args.set}.yaml"
    result = {"set": args.set,
              "provenance": {**run_out["provenance"], "truth": {str(tf.relative_to(ROOT)): _sha256(tf)}},
              **scored(run_out["states"], hop_set(args.set), truth)}
    out = RESULTS / f"p-extension-{args.set}.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    for n, m in result["verifiers"].items():
        print(f"{n:28} {m['class']:26} true {m['true_verified']}/{m['true_hops']}, "
              f"false verified {m['false_verified']}/{m['false_hops']}, true contradicted {m['true_contradicted']}")


def entry_anchors() -> dict:
    return yaml.safe_load((HERE / "entry_anchors.yaml").read_text())


def chain_check() -> dict:
    """Does a chain of VERIFIED true hops (bridge + the frozen golden local hops) lead from the
    Spike P source endpoint to the §12 terminal? Frozen §12 classifier, frozen connector."""
    s, truth = hop_set("current"), truth_of("current")["truth"]
    states = json.loads((RUNS / "current" / "states.json").read_text())["states"]
    analyses = json.loads((RUNS / "current" / "analyses.json").read_text())
    ev, ev_truth = verify.hop_set("eval"), verify.truth_of("eval")["truth"]
    anchors12 = yaml.safe_load((ROOT / "experiments" / "hop_chain" / "anchors.yaml").read_text())
    out = {}
    for fid, fixture in s["fixtures"].items():
        rels = relations(fixture["language"])
        for rev in ("base", "head"):
            analysis = analyses[f"{fid}|{rev}"]
            true_bridge = [h for h in s["hops"] if h["fixture"] == fid and h["revision"] == rev
                           and truth[h["id"]]["label"] and states[h["id"]]["state"] == "VERIFIED"]
            local = [h for h in ev["hops"] if h["fixture"] == fid and h["revision"] == rev
                     and ev_truth[h["id"]]["label"]]
            edges = verified_edges(true_bridge + local, fixture, rels, analysis)
            entry = tuple(entry_anchors()[fid][rev])
            got = classify(edges, fid, rev, fixture, entry, anchors12[fid][rev])
            out[f"{fid}/{rev}"] = {**got, "verified_bridge_hops": [h["id"] for h in true_bridge]}
    return out


def verified_edges(hops: list[dict], fixture: dict, rels: dict, analysis: dict) -> list[dict]:
    edges = []
    for h in hops:
        c = {k: h[k] for k in ("revision", "relation", "from", "to")}
        res = hoplib.resolve(c, text_reader(fixture), rels, analysis, fixture["language"])
        if hoplib.verdict(c, res, rels, analysis) == "VERIFIED":
            edges.append({"id": h["id"], "relation": h["relation"], "a": res.node_from, "b": res.node_to})
    return edges


def classify(edges: list[dict], fid: str, rev: str, fixture: dict, entry: tuple, a12: dict) -> dict:
    """Frozen §12 classifier with the frozen C2 connector (Go) from `entry` to the §12 terminal."""
    conn = C.load_frozen(fid, rev) if fixture["language"] == "go" else None
    same = (lambda a, b, k=conn: k.same_object(a, b) == C.SAME) if conn else None
    return chain.classify(edges, entry, tuple(a12["terminal"]), a12["needs_qualifier"], same)


def chain_cmd(_args: argparse.Namespace) -> None:
    result = {"chains": chain_check()}
    (RESULTS / "p-extension-chain.json").write_text(json.dumps(result, indent=2, default=list) + "\n")
    print(json.dumps(result, indent=1, default=list))


# every pre-registered §14 verifier, from the frozen relations.yaml (not from whatever a result holds)
BRIDGE_VERIFIERS = sorted(verifier_key(lang, n) for lang, rels in BRIDGE["relations"].items() for n in rels)


def cal_failures(cal: dict) -> dict:
    """The held-out cal alone: UNSAFE, tool failure, or a pre-registered verifier BLIND/missing."""
    v = cal["verifiers"]
    return {"unsafe": sorted(n for n, m in v.items() if m["class"] == "UNSAFE"),
            "tool_failure": sorted(n for n, m in v.items() if m["class"] == "INCONCLUSIVE_TOOL_FAILURE"),
            "calibration_blind": [n for n in BRIDGE_VERIFIERS if v.get(n, {}).get("class") in ("BLIND", None)]}


def cal_gate(path: Path = RESULTS / "p-extension-cal.json") -> list[str]:
    """§14.8: current runs only after cal passed, with the files cal ran on unchanged."""
    if not path.exists():
        return ["no cal result"]
    cal = json.loads(path.read_text())
    problems = [f"{f} changed since cal" for f, h in cal["provenance"]["files"].items()
                if not (ROOT / f).exists() or _sha256(ROOT / f) != h]
    return problems + [f"cal {k}: {v}" for k, v in cal_failures(cal).items() if v]


def routing(cal: dict, current: dict | None, chains: dict | None) -> dict:
    """§14.6, first match wins. UNSAFE: any verifier on cal, or on the current check (which also
    judges the frozen object_composition hops Caddy needs). CALIBRATION_BLIND: a §14 verifier
    verified no true hop of the held-out cal (PARTIAL is fine). CAPABILITY_GAPS: a revision does
    not close from the real entry to the §12 terminal; it is recorded, no relation is added.
    When cal fails, current never runs and the decision is cal's alone."""
    cur = current["verifiers"] if current else {}
    names = sorted(set(cal["verifiers"]) | set(cur) | set(BRIDGE_VERIFIERS))
    classes = {n: {"cal": cal["verifiers"].get(n, {}).get("class"), "current": cur.get(n, {}).get("class")}
               for n in names}
    unsafe = [n for n, c in classes.items() if "UNSAFE" in c.values()]
    tool = [n for n, c in classes.items() if "INCONCLUSIVE_TOOL_FAILURE" in c.values()]
    blind = cal_failures(cal)["calibration_blind"]
    if current is None and not (unsafe or tool or blind):
        raise ValueError("cal passed: current must run before a decision")
    gaps = {k: v["class"] for k, v in sorted((chains or {}).items()) if v["class"] != "FULL_CHAIN"}
    if unsafe:
        decision = "UNSAFE"
    elif tool:
        decision = "INCONCLUSIVE_TOOL_FAILURE"
    elif blind:
        decision = "CALIBRATION_BLIND"
    elif gaps:
        decision = "CAPABILITY_GAPS"
    else:
        decision = "LOOP_CLOSED"
    return {"decision": decision, "current_run": current is not None, "classes": classes,
            "unsafe": unsafe, "tool_failure": tool, "calibration_blind": blind, "gaps": gaps}


def decide(_args: argparse.Namespace) -> None:
    cal = json.loads((RESULTS / "p-extension-cal.json").read_text())
    current = chains = None
    if (RESULTS / "p-extension-current.json").exists():
        current = json.loads((RESULTS / "p-extension-current.json").read_text())
        chains = json.loads((RESULTS / "p-extension-chain.json").read_text())["chains"]
    result = routing(cal, current, chains)
    (RESULTS / "p-extension-decision.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "run", "score"):
        sub.add_parser(name).add_argument("--set", choices=SETS, required=True)
    sub.add_parser("chain")
    sub.add_parser("decide")
    args = ap.parse_args()
    {"check": check, "run": run, "score": score, "chain": chain_cmd, "decide": decide}[args.cmd](args)


if __name__ == "__main__":
    main()
