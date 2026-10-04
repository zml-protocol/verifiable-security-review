"""P-Hybrid-1: provider-only single-hop verification (PREREGISTRATION.md §10). No LLM.

    uv run python experiments/hop_verify/verify.py check --set dev|cal|eval   # schema, anchors, truth (no verifier)
    uv run python experiments/hop_verify/verify.py run --set dev|cal|eval     # CodeQL databases, verifiers, hop states
    uv run python experiments/hop_verify/verify.py score --set cal|eval       # states + truth -> results/
    uv run python experiments/hop_verify/verify.py decide                     # cal + eval scores -> routing (§10.6)

`run` never reads truth/: the verifiers see only the hop sets (id, fixture,
revision, relation, from, to) and the source at the hop's revision.
"""

import argparse
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
sys.path.insert(0, str(ROOT / "experiments" / "provider_reach"))

import reach  # pinned CodeQL, Go environment, commit trees

RUNS = ROOT / "runs" / "hop_verify"
RESULTS = ROOT / "results"
SETS = ("dev", "cal", "eval")
HOP_KEYS = {"id", "fixture", "revision", "relation", "from", "to"}
ENDPOINT_KEYS = {"file", "start_line", "end_line", "expression"}
STATES = ("VERIFIED", "UNVERIFIED", "CONTRADICTED", "ANCHOR_REJECTED", "TOOL_FAILURE")


class AnchorError(Exception):
    pass


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def relations() -> dict:
    return load(HERE / "relations.yaml")


def hop_set(name: str) -> dict:
    return load(HERE / "sets" / f"{name}.yaml")


def truth_of(name: str) -> dict:
    return load(HERE / "truth" / f"{name}.yaml")


# ---- anchors -------------------------------------------------------------------


def locate(text: str, ep: dict, byte_columns: bool) -> tuple[int, int]:
    """Where `ep`'s expression starts inside its span: (line, column), both 1-based.

    Whitespace runs (line breaks included) compare as one space. The expression must
    occur exactly once in the span. Go columns count bytes, Python columns characters,
    as the CodeQL extractors do."""
    lines = text.splitlines()
    lo, hi = ep["start_line"], ep["end_line"]
    if not 1 <= lo <= hi <= len(lines):
        raise AnchorError(f"span {lo}-{hi} outside {ep['file']} ({len(lines)} lines)")
    chars: list[str] = []
    where: list[tuple[int, int] | None] = []
    space = False
    for n in range(lo, hi + 1):
        col = 1
        for ch in lines[n - 1]:
            if ch.isspace():
                space = bool(chars)
            else:
                if space:
                    chars.append(" ")
                    where.append(None)
                    space = False
                chars.append(ch)
                where.append((n, col))
            col += len(ch.encode()) if byte_columns else 1
        space = bool(chars)
    norm, expr = "".join(chars), " ".join(ep["expression"].split())
    starts = [i for i in range(len(norm)) if norm.startswith(expr, i)] if expr else []
    if len(starts) != 1:
        raise AnchorError(f"expression occurs {len(starts)} times in {ep['file']}:{lo}-{hi}")
    return where[starts[0]]


def source(fixture: dict, revision: str, file: str) -> str | None:
    path = reach.tree(ROOT / fixture["repo"], fixture["commits"][revision]) / file
    return path.read_text() if path.is_file() else None


def anchors(fixture: dict, hop: dict) -> tuple[tuple[int, int], tuple[int, int]]:
    byte_columns = fixture["language"] == "go"
    out = []
    for side in ("from", "to"):
        ep = hop[side]
        text = source(fixture, hop["revision"], ep["file"])
        if text is None:
            raise AnchorError(f"{ep['file']} does not exist at {hop['revision']}")
        out.append(locate(text, ep, byte_columns))
    return out[0], out[1]


# ---- check (before the freeze; no verifier runs) ---------------------------------


def check_set(name: str) -> list[str]:
    """Problems with a hop set and its truth; empty when it may be frozen."""
    s, t, rel = hop_set(name), truth_of(name), relations()["relations"]
    truth, problems, seen = t["truth"], [], {}
    for hop in s["hops"]:
        hid = hop.get("id")
        if set(hop) != HOP_KEYS:
            problems.append(f"{hid}: keys {sorted(set(hop) ^ HOP_KEYS)} (hops carry no truth)")
            continue
        for side in ("from", "to"):
            if set(hop[side]) != ENDPOINT_KEYS:
                problems.append(f"{hid}: {side} keys {sorted(hop[side])}")
        fixture = s["fixtures"].get(hop["fixture"])
        if fixture is None or hop["revision"] not in fixture["commits"]:
            problems.append(f"{hid}: unknown fixture or revision")
            continue
        if hop["relation"] not in rel or rel[hop["relation"]]["language"] != fixture["language"]:
            problems.append(f"{hid}: relation {hop['relation']} does not apply to {fixture['language']}")
        key = json.dumps([hop["fixture"], hop["revision"], hop["relation"], hop["from"], hop["to"]],
                         sort_keys=True)
        if key in seen:
            problems.append(f"{hid}: duplicate of {seen[key]}")
        seen[key] = hid
        entry = truth.get(hid)
        if entry is None or not isinstance(entry.get("label"), bool):
            problems.append(f"{hid}: no truth label")
            continue
        if entry["label"] is False and not (entry.get("kind") and entry.get("reason")):
            problems.append(f"{hid}: a false hop needs a kind and a reason")
        try:
            anchors(fixture, hop)
            if entry.get("expect") == "anchor_rejected":
                problems.append(f"{hid}: expected the anchor check to reject it, but it anchors")
        except AnchorError as e:
            if entry.get("expect") != "anchor_rejected":
                problems.append(f"{hid}: {e}")
    extra = set(truth) - {h.get("id") for h in s["hops"]}
    if extra:
        problems.append(f"truth for unknown hops: {sorted(extra)}")
    return problems


def check(args: argparse.Namespace) -> None:
    problems = check_set(args.set)
    for p in problems:
        print(p)
    n = len(hop_set(args.set)["hops"])
    print(f"{args.set}: {n} hops, {len(problems)} problems")
    sys.exit(1 if problems else 0)


# ---- run ----------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_query(db: Path, query: Path, out: Path, env: dict) -> list[list]:
    bqrs = out.with_suffix(".bqrs")
    proc = subprocess.run([str(reach.CODEQL), "query", "run", f"--database={db}", f"--output={bqrs}",
                           str(query)], capture_output=True, text=True, env=env, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"{query.name}: {proc.stderr[-3000:]}")
    proc = subprocess.run([str(reach.CODEQL), "bqrs", "decode", "--format=json", str(bqrs)],
                          capture_output=True, text=True, env=env, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"decode {query.name}: {proc.stderr[-3000:]}")
    tuples = json.loads(proc.stdout)["#select"]["tuples"]
    out.write_text(json.dumps(tuples))
    return tuples


def analyze(fixture_id: str, fixture: dict, revision: str, needed: set[str], workdir: Path) -> dict:
    """Database + shape query + the verifiers `needed`; every attempt starts from nothing."""
    rel = relations()
    lang = fixture["language"]
    shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True)
    env = {**os.environ, **(reach.go_env() if lang == "go" else {})}
    src = reach.tree(ROOT / fixture["repo"], fixture["commits"][revision])
    db = workdir / "db"
    create = [str(reach.CODEQL), "database", "create", str(db), f"--language={lang}",
              f"--source-root={src}", "--overwrite"]
    if fixture.get("db_build"):
        create.append(f"--command={fixture['db_build']}")
    proc = subprocess.run(create, capture_output=True, text=True, env=env, check=False)
    if proc.returncode != 0:
        return {"status": "tool_failure", "stage": "database", "error": proc.stderr[-3000:]}
    queries = HERE / "queries" / lang
    out = {"status": "ok", "rows": {}}
    try:
        out["shapes"] = run_query(db, queries / rel["shapes"][lang], workdir / "shapes.json", env)
        for name in sorted(needed):
            q = rel["relations"][name]["verifier"]
            out["rows"][name] = run_query(db, queries / q, workdir / f"{name}.json", env)
    except RuntimeError as e:
        return {"status": "tool_failure", "stage": "query", "error": str(e)}
    return out


def _starts_at(row_file: str, row_line: int, row_col: int, file: str, at: tuple[int, int]) -> bool:
    return row_file == file and (row_line, row_col) == at


def judge(hop: dict, fixture: dict, analysis: dict) -> dict:
    """The provider's state for one hop (§10.5)."""
    try:
        a_from, a_to = anchors(fixture, hop)
    except AnchorError as e:
        return {"state": "ANCHOR_REJECTED", "detail": str(e)}
    if analysis["status"] != "ok":
        return {"state": "TOOL_FAILURE", "detail": f"{analysis['stage']}: {analysis['error'][:300]}"}
    spec = relations()["relations"][hop["relation"]]
    shapes = analysis["shapes"]
    extracted = {r[1] for r in shapes if r[0] == "file"}
    missing = [hop[s]["file"] for s in ("from", "to") if hop[s]["file"] not in extracted]
    if missing:
        return {"state": "TOOL_FAILURE", "detail": f"not extracted: {missing}"}

    def shape_ok(side: str, at: tuple[int, int]) -> bool:
        role, kinds, file = spec[side]["role"], set(spec[side]["kinds"]), hop[side]["file"]
        for kind, f, sl, sc, el in shapes:
            if kind not in kinds or f != file:
                continue
            if role == "node" and (sl, sc) == at:
                return True
            if role == "inside" and sl <= at[0] <= el:
                return True
        return False

    bad = [side for side, at in (("from", a_from), ("to", a_to)) if not shape_ok(side, at)]
    if bad:
        return {"state": "CONTRADICTED", "detail": f"shape: {', '.join(bad)} names no "
                + " / ".join(",".join(spec[s]["kinds"]) for s in bad)}
    inside = spec["to"]["role"] == "inside"
    for ff, fl, fc, tf, t1, t2 in analysis["rows"].get(hop["relation"], []):
        if not _starts_at(ff, fl, fc, hop["from"]["file"], a_from):
            continue
        if inside and tf == hop["to"]["file"] and t1 <= a_to[0] <= t2:
            return {"state": "VERIFIED", "detail": f"resolved to {tf}:{t1}-{t2}"}
        if not inside and _starts_at(tf, t1, t2, hop["to"]["file"], a_to):
            return {"state": "VERIFIED", "detail": "relation instance found"}
    return {"state": "UNVERIFIED", "detail": "no relation instance links the two endpoints"}


def provenance(s: dict) -> dict:
    files = [HERE / "relations.yaml", HERE / "verify.py", HERE / "sets" / f"{s['set']}.yaml",
             *sorted((HERE / "queries").rglob("*.ql*"))]
    return {"codeql": reach.CODEQL_TAG,
            "files": {str(p.relative_to(ROOT)): _sha256(p) for p in files}}


def run(args: argparse.Namespace) -> None:
    s = hop_set(args.set)
    by_target: dict[tuple[str, str], set[str]] = {}
    for hop in s["hops"]:
        by_target.setdefault((hop["fixture"], hop["revision"]), set()).add(hop["relation"])
    analyses = {}
    for (fid, rev), needed in sorted(by_target.items()):
        print(f"[{args.set}] {fid} {rev}: {', '.join(sorted(needed))}", flush=True)
        analyses[(fid, rev)] = analyze(fid, s["fixtures"][fid], rev, needed, RUNS / args.set / fid / rev)
        if analyses[(fid, rev)]["status"] != "ok":
            print(f"  tool failure at {analyses[(fid, rev)]['stage']}", flush=True)
    states = {}
    for hop in s["hops"]:
        states[hop["id"]] = {"relation": hop["relation"], "fixture": hop["fixture"],
                             "revision": hop["revision"],
                             **judge(hop, s["fixtures"][hop["fixture"]], analyses[(hop["fixture"], hop["revision"])])}
    out = RUNS / args.set / "states.json"
    out.write_text(json.dumps({"set": args.set, "provenance": provenance(s), "states": states}, indent=2))
    counts = {k: sum(v["state"] == k for v in states.values()) for k in STATES}
    print(f"{out.relative_to(ROOT)}: {counts}")


# ---- score & decide --------------------------------------------------------------


def classify(m: dict) -> str:
    if m["false_verified"] or m["true_contradicted"]:
        return "UNSAFE"
    if m["tool_failures"]:
        return "INCONCLUSIVE_TOOL_FAILURE"
    if not m["true_hops"]:
        return "NO_TRUE_HOPS"
    if m["true_verified"] == m["true_hops"]:
        return "SUPPORTED"
    return "PARTIAL" if m["true_verified"] else "BLIND"


def score_states(states: dict, truth: dict) -> dict:
    per: dict[str, dict] = {}
    by_kind: dict[str, dict] = {}
    for hid, st in sorted(states.items()):
        t = truth[hid]
        m = per.setdefault(st["relation"], {
            "true_hops": 0, "false_hops": 0, "true_verified": 0, "false_verified": 0,
            "true_contradicted": 0, "false_contradicted": 0, "true_unverified": 0,
            "false_unverified": 0, "caught_by_anchor": 0, "tool_failures": 0, "hops": {}})
        m["hops"][hid] = {"label": t["label"], "state": st["state"], "name": t.get("name", hid)}
        state = st["state"]
        if state == "TOOL_FAILURE":
            m["tool_failures"] += 1
            continue
        if state == "ANCHOR_REJECTED":
            if t["label"]:
                m["tool_failures"] += 1  # impossible after `check`; never silently dropped
            else:
                m["caught_by_anchor"] += 1
            continue
        side = "true" if t["label"] else "false"
        m[f"{side}_hops"] += 1
        m[f"{side}_{state.lower()}"] += 1
        if not t["label"]:
            k = by_kind.setdefault(t.get("kind", "?"), {s: 0 for s in STATES})
            k[state] += 1
    for m in per.values():
        m["false_verification_rate"] = m["false_verified"] / m["false_hops"] if m["false_hops"] else None
        m["true_hop_coverage"] = m["true_verified"] / m["true_hops"] if m["true_hops"] else None
        verified = m["true_verified"] + m["false_verified"]
        m["verification_precision"] = m["true_verified"] / verified if verified else None
        m["class"] = classify(m)
    return {"relations": per, "false_hops_by_mutation": by_kind}


def score(args: argparse.Namespace) -> None:
    run_out = json.loads((RUNS / args.set / "states.json").read_text())
    truth = truth_of(args.set)["truth"]
    if set(truth) != set(run_out["states"]):
        sys.exit("states and truth cover different hops")
    truth_file = HERE / "truth" / f"{args.set}.yaml"
    provenance = {**run_out["provenance"],
                  "truth": {str(truth_file.relative_to(ROOT)): _sha256(truth_file)}}
    result = {"set": args.set, "provenance": provenance, **score_states(run_out["states"], truth)}
    out = RESULTS / f"p-hybrid-1-{args.set}.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    for name, m in result["relations"].items():
        print(f"{name:22} {m['class']:26} true {m['true_verified']}/{m['true_hops']} verified, "
              f"false verified {m['false_verified']}/{m['false_hops']}, "
              f"true contradicted {m['true_contradicted']}, anchor-caught {m['caught_by_anchor']}")
    print(f"-> {out.relative_to(ROOT)}")


def routing(cal: dict, ev: dict, gaps: list[str]) -> dict:
    """§10.6: any UNSAFE blocks Hybrid-2. Otherwise a relation is eligible for Hybrid-2 only
    when its evaluation class is SUPPORTED or PARTIAL and its held-out calibration actually
    ran (present, not INCONCLUSIVE_TOOL_FAILURE); an eligible gap relation opens a
    limited-scope Hybrid-2 for the eligible relations only."""
    classes = {name: {"cal": cal["relations"].get(name, {}).get("class"),
                      "eval": ev["relations"].get(name, {}).get("class")}
               for name in sorted(set(cal["relations"]) | set(ev["relations"]))}
    unsafe = sorted(n for n, c in classes.items() if "UNSAFE" in c.values())
    inconclusive = sorted(n for n, c in classes.items()
                          if "INCONCLUSIVE_TOOL_FAILURE" in c.values() or c["cal"] is None)
    eligible = sorted(n for n, c in classes.items()
                      if c["eval"] in ("SUPPORTED", "PARTIAL") and n not in inconclusive)
    if unsafe:
        decision = "NO_HYBRID_2"
    elif set(eligible) & set(gaps):
        decision = "HYBRID_2_LIMITED_SCOPE"
    elif set(inconclusive) & set(gaps):
        decision = "INCONCLUSIVE_TOOL_FAILURE"
    else:
        decision = "NO_NEW_CAPABILITY"
    limited = decision == "HYBRID_2_LIMITED_SCOPE"
    return {"decision": decision, "classes": classes, "unsafe": unsafe,
            "inconclusive": inconclusive,
            "verifiable_in_hybrid_2": eligible if limited else [],
            "blind_spots": sorted(n for n in classes if n not in eligible) if limited else []}


def decide(_args: argparse.Namespace) -> None:
    cal = json.loads((RESULTS / "p-hybrid-1-cal.json").read_text())
    ev = json.loads((RESULTS / "p-hybrid-1-eval.json").read_text())
    result = routing(cal, ev, relations()["gaps"])
    out = RESULTS / "p-hybrid-1-decision.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("check", "run", "score"):
        sub.add_parser(name).add_argument("--set", choices=SETS, required=True)
    sub.add_parser("decide")
    args = p.parse_args()
    {"check": check, "run": run, "score": score, "decide": decide}[args.cmd](args)


if __name__ == "__main__":
    main()
