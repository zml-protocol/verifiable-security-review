"""Spike P: can a structural provider recover the reachability facts agents did not cite?

    uv run python experiments/provider_reach/reach.py fetch-codeql   # pinned bundle, sha-checked
    uv run python experiments/provider_reach/reach.py run --provider trailmark|codeql [--spec ...]
    uv run python experiments/provider_reach/reach.py score

Each provider gets only the preregistered endpoints (endpoints.yaml) and must
recover the golden path-fact locations on its own; the scorer is the only
code that reads the goldens. Rules: PREREGISTRATION.md §9.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from collections import defaultdict
from pathlib import Path

import yaml

from spike.models import Golden

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT / ".cache"
OUT = ROOT / "runs" / "provider_reach"

TRAILMARK = "trailmark==0.5.0"
CODEQL_TAG = "codeql-bundle-v2.27.1"
CODEQL_SHA256 = "1d380f79896ededc654c7b21fafb3360136f1aeb678ad4df4df9af3910c6b815"
CODEQL_URL = f"https://github.com/github/codeql-action/releases/download/{CODEQL_TAG}/codeql-bundle-linux64.tar.gz"
CODEQL_TERMS = "https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md (read 2026-09-28)"
CODEQL_HOME = CACHE / "toolchains" / CODEQL_TAG
CODEQL = CODEQL_HOME / "codeql" / "codeql"

# Evidence granularities that may cover a golden line (§9: a function node that
# merely spans the line is too coarse to count).
LINE_LEVEL = {"dataflow"}
CALIBRATION = ROOT / "results" / "spike-p-calibration.json"
SIDES = ("base", "head")


def load_spec(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def go_env() -> dict:
    """The pinned Go toolchain of fixtures/_truth/goenv.sh, as an environment."""
    out = subprocess.run(
        ["bash", "-c", f"source {ROOT}/fixtures/_truth/goenv.sh && env -0"],
        capture_output=True, check=True,
    ).stdout
    return dict(item.split("=", 1) for item in out.decode().split("\0") if "=" in item)


def tree(repo: Path, commit: str) -> Path:
    """The commit's files, materialized once (read-only use)."""
    dest = CACHE / "trees" / repo.name / commit
    if not dest.exists():
        tmp = Path(tempfile.mkdtemp(dir=CACHE))
        archive = subprocess.run(["git", "-C", str(repo), "archive", commit],
                                 capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", str(tmp)], input=archive, check=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp.rename(dest)
    return dest


# ---- providers ----------------------------------------------------------------


def run_trailmark(fixture: dict, src: Path, ends: dict) -> dict:
    """Function-level path over resolved `calls` edges between the endpoint functions."""
    proc = subprocess.run(
        ["uvx", "--from", TRAILMARK, "trailmark", "analyze", "--language", fixture["language"], "."],
        cwd=src, capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        return {"status": "tool_failure", "error": proc.stderr[-2000:]}
    graph = json.loads(proc.stdout)
    nodes = graph["nodes"]

    def enclosing(file: str, line: int) -> str | None:
        best = None
        for nid, n in nodes.items():
            loc = n.get("location") or {}
            inside = (n.get("kind") in ("function", "method")
                      and loc.get("file_path", "").lstrip("./") == file
                      and loc["start_line"] <= line <= loc["end_line"])
            if inside and (best is None or loc["start_line"] >= nodes[best]["location"]["start_line"]):
                best = nid
        return best

    start = enclosing(ends["source"]["file"], ends["source"]["line"])
    goal = enclosing(ends["sink"]["file"], ends["sink"]["line"])
    succ = defaultdict(list)
    for e in graph["edges"]:
        if e["kind"] == "calls" and e["confidence"] in ("certain", "inferred") \
                and not e["target"].startswith("proxy."):
            succ[e["source"]].append(e["target"])
    path, frontier, seen = None, [[start]] if start else [], {start}
    while frontier and path is None:
        nxt = []
        for p in frontier:
            if p[-1] == goal:
                path = p
                break
            for t in succ[p[-1]]:
                if t not in seen:
                    seen.add(t)
                    nxt.append(p + [t])
        frontier = nxt
    items = [
        {"file": nodes[n]["location"]["file_path"].lstrip("./"),
         "start_line": nodes[n]["location"]["start_line"],
         "end_line": nodes[n]["location"]["end_line"], "granularity": "function", "node": n}
        for n in (path or [])
    ]
    return {"status": "ok", "source_function": start, "sink_function": goal,
            "function_path_found": path is not None, "paths": [items] if items else []}


def endpoints_qll(ends: dict) -> str:
    def pred(name: str, e: dict) -> str:
        return (f'predicate {name}(string file, int line, string name) {{\n'
                f'  file = "{e["file"]}" and line = {e["line"]} and name = "{e["name"]}"\n}}\n')
    return pred("sourceAt", ends["source"]) + "\n" + pred("sinkAt", ends["sink"])


def prepare_codeql_workdir(workdir: Path, lang: str, ends: dict) -> dict[str, Path]:
    """Start every attempt from nothing, so a rerun after a plumbing fix (§9.5) or a
    tool failure (§9.6) can never pick up a stale pack, database or result."""
    paths = {"db": workdir / "db", "pack": workdir / "pack",
             "taint": workdir / "result.sarif", "resolve": workdir / "resolve.sarif"}
    for key in ("db", "pack"):
        shutil.rmtree(paths[key], ignore_errors=True)
    for key in ("taint", "resolve"):
        paths[key].unlink(missing_ok=True)
    workdir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(HERE / "queries" / lang, paths["pack"])
    (paths["pack"] / "Endpoints.qll").write_text(endpoints_qll(ends))
    return paths


def _sarif_results(path: Path) -> list[dict]:
    return json.loads(path.read_text())["runs"][0].get("results", [])


def run_codeql(fixture: dict, src: Path, ends: dict, workdir: Path) -> dict:
    lang = fixture["language"]
    env = {**os.environ, **(go_env() if lang == "go" else {})}
    w = prepare_codeql_workdir(workdir, lang, ends)
    db = w["db"]
    create = [str(CODEQL), "database", "create", str(db), f"--language={lang}",
              f"--source-root={src}", "--overwrite"]
    if fixture.get("build"):
        create.append(f"--command={fixture['build']}")
    proc = subprocess.run(create, capture_output=True, text=True, env=env, check=False)
    if proc.returncode != 0:
        return {"status": "tool_failure", "stage": "database", "error": proc.stderr[-3000:]}
    for query, out in (("ResolveEndpoints.ql", w["resolve"]), ("ReachTaint.ql", w["taint"])):
        proc = subprocess.run(
            [str(CODEQL), "database", "analyze", str(db), str(w["pack"] / query),
             "--format=sarif-latest", f"--output={out}", "--rerun"],
            capture_output=True, text=True, env=env, check=False,
        )
        if proc.returncode != 0:
            return {"status": "tool_failure", "stage": f"analyze {query}", "error": proc.stderr[-3000:]}
    roles = [r["message"]["text"] for r in _sarif_results(w["resolve"])]
    counts = {"source_nodes": roles.count("source"), "sink_nodes": roles.count("sink")}
    if not (counts["source_nodes"] and counts["sink_nodes"]):
        # an endpoint that matched no node never entered the recovery test (§9.4)
        return {"status": "endpoint_failure", "stage": "resolve_endpoints", **counts, "paths": []}
    paths = []
    for res in _sarif_results(w["taint"]):
        for flow in res.get("codeFlows", []):
            for thread in flow.get("threadFlows", []):
                items = []
                for step in thread["locations"]:
                    phys = step["location"]["physicalLocation"]
                    region = phys.get("region", {})
                    items.append({
                        "file": phys["artifactLocation"]["uri"],
                        "start_line": region.get("startLine"),
                        "end_line": region.get("endLine", region.get("startLine")),
                        "granularity": "dataflow",
                        "text": step["location"].get("message", {}).get("text", ""),
                    })
                paths.append(items)
    return {"status": "ok", **counts, "paths": paths}


def run(args: argparse.Namespace) -> None:
    spec = load_spec(args.spec)
    out = args.out / args.provider
    for fid, fixture in spec["fixtures"].items():
        repo = ROOT / fixture["repo"]
        for side in SIDES:
            src = tree(repo, fixture["commits"][side])
            ends = fixture["endpoints"][side]
            dest = out / fid / side
            dest.mkdir(parents=True, exist_ok=True)
            if args.provider == "trailmark":
                result = run_trailmark(fixture, src, ends)
            else:
                result = run_codeql(fixture, src, ends, dest)
            result |= {"provider": args.provider, "fixture": fid, "side": side, "endpoints": ends}
            (dest / "evidence.json").write_text(json.dumps(result, indent=2))
            n = len(result.get("paths", []))
            print(f"{args.provider:9} {fid:30} {side}: {result['status']} paths={n}", flush=True)


# ---- scoring (the only place goldens are read) --------------------------------


def covers(item: dict, file: str, lo: int, hi: int) -> bool:
    return (item["granularity"] in LINE_LEVEL and item["file"] == file
            and item["start_line"] <= hi and lo <= item["end_line"])


def on_path(path: list[dict], loc: dict) -> bool:
    """A location is on a path when every preregistered anchor of it is (§9.4).

    Without anchors the whole span is one anchor. Anchors keep a wide span from
    counting as recovered because the path merely touches one of its lines.
    """
    anchors = [(a, a) for a in loc.get("anchors", [])] or [_span(loc["lines"])]
    return all(any(covers(i, loc["file"], lo, hi) for i in path) for lo, hi in anchors)


def _locations(fixture: dict, side: str) -> list[dict]:
    locs = fixture["locations"]
    return locs[side] if isinstance(locs, dict) else locs


def resolve_expressible(spec: dict, calibration: Path) -> dict:
    """Replace every `calibrate` entry with the pilot's verdict (§9.5); fail if missing."""
    table = {p: dict(rels) for p, rels in spec["expressible"].items()}
    pending = [(p, r) for p, rels in table.items() for r, v in rels.items() if v == "calibrate"]
    if pending:
        if not calibration.exists():
            sys.exit(f"expressibility still to be calibrated by the pilot: {pending}")
        data = json.loads(calibration.read_text())
        providers = {p for p, _ in pending}
        if data.get("provider") not in providers:
            sys.exit(f"calibration is for {data.get('provider')!r}, expected one of {sorted(providers)}")
        missing = [r for p, r in pending if r not in data["relations"]]
        if missing:
            sys.exit(f"calibration lacks relations {missing}")
        for p, r in pending:
            table[p][r] = data["relations"][r]["expressible"]
    return table


def score(args: argparse.Namespace) -> None:
    spec = load_spec(args.spec)
    report: dict = {"locations": [], "instances": [], "facts": []}
    table = resolve_expressible(spec, args.calibration)
    report["expressible"] = table
    for provider, expressible in table.items():
        name = provider.split("-")[0]
        for fid, fixture in spec["fixtures"].items():
            golden = Golden.load(ROOT / "fixtures" / fid / "golden.yaml")
            for side in SIDES:
                fact_id = f"{side}-{fixture['path_fact']}"
                fact = next(f for h in golden.hypotheses.values() for f in h.facts if f.id == fact_id)
                locs = _locations(fixture, side)
                # the relation table must describe exactly the golden fact's locations
                golden_locs = sorted((loc.path, *loc.span()) for loc in fact.evidence_sets[0])
                assert golden_locs == sorted((x["file"], *_span(x["lines"])) for x in locs), (fid, side)
                ev_path = args.out / name / fid / side / "evidence.json"
                ev = json.loads(ev_path.read_text()) if ev_path.exists() else {"status": "missing"}
                # a run whose endpoints resolved to nothing is a plumbing failure, never a
                # recovery result, whatever its status says (§9.4)
                ok = (ev.get("status") == "ok" and ev.get("source_nodes", 1) > 0
                      and ev.get("sink_nodes", 1) > 0)
                paths = ev.get("paths", [])

                for x in locs:
                    hit = any(on_path(p, x) for p in paths)
                    if not ok:
                        cat = "TOOL_FAILURE"
                    elif not expressible[x["relation"]]:
                        # reported, but a preregistered non-expressible relation never counts
                        cat = "HIT_BUT_NOT_EXPRESSIBLE" if hit else "NOT_EXPRESSIBLE"
                    else:
                        cat = "SUPPORTED_AND_RECOVERED" if hit else "EXPRESSIBLE_NOT_RECOVERED"
                    report["locations"].append({"provider": provider, "fixture": fid, "side": side,
                                                "file": x["file"], "lines": x["lines"],
                                                "relation": x["relation"], "category": cat})
                # a relation instance (fixture x side x relation) needs ONE path through all its locations
                for rel in sorted({x["relation"] for x in locs}):
                    members = [x for x in locs if x["relation"] == rel]
                    report["instances"].append({
                        "provider": provider, "fixture": fid, "side": side, "relation": rel,
                        "expressible": expressible[rel], "tool_ok": ok,
                        "recovered": ok and expressible[rel]
                        and any(all(on_path(p, x) for x in members) for p in paths),
                    })
                report["facts"].append({
                    "provider": provider, "fixture": fid, "side": side, "fact": fact_id,
                    "recovered": ok and all(expressible[x["relation"]] for x in locs)
                    and any(all(on_path(p, x) for x in locs) for p in paths),
                    "function_path_found": ev.get("function_path_found"),
                })

    # §9.6: per relation class, judged only over providers preregistered as able to express it.
    viability = {}
    for rel in sorted({i["relation"] for i in report["instances"]}):
        rows = [i for i in report["instances"] if i["relation"] == rel and i["expressible"]]
        by_provider = defaultdict(list)
        for i in rows:
            by_provider[i["provider"]].append(i)
        recovered = sorted(p for p, xs in by_provider.items() if all(x["recovered"] for x in xs))
        failed_tools = sorted(p for p, xs in by_provider.items() if not all(x["tool_ok"] for x in xs))
        if recovered:
            state = "RECOVERED"
        elif not by_provider:
            state = "NOT_EXPRESSIBLE_BY_ANY"
        elif failed_tools:
            state = "INCONCLUSIVE_TOOL_FAILURE"
        else:
            state = "EXPRESSIBLE_NOT_RECOVERED"
        viability[rel] = {"state": state, "recovered_by": recovered, "tool_failures": failed_tools}
    report["relation_viability"] = viability
    states = {v["state"] for v in viability.values()}
    if "EXPRESSIBLE_NOT_RECOVERED" in states:
        report["decision"] = "B_GAPS_RECORDED"
    elif "INCONCLUSIVE_TOOL_FAILURE" in states:
        report["decision"] = "INCONCLUSIVE_TOOL_FAILURE"
    elif "NOT_EXPRESSIBLE_BY_ANY" in states:
        report["decision"] = "B_LIMITED_SCOPE_TO_1A"
    else:
        report["decision"] = "B_PROCEEDS_TO_1A"
    providers = {f["provider"] for f in report["facts"]}
    report["providers_recovering_every_fact"] = sorted(
        p for p in providers if all(f["recovered"] for f in report["facts"] if f["provider"] == p)
    )
    counts: dict = {}
    for row in report["locations"]:
        key = f"{row['provider']}/{row['relation']}"
        counts.setdefault(key, defaultdict(int))[row["category"]] += 1
    report["location_categories"] = counts
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("relation_viability", "decision",
                                             "providers_recovering_every_fact")}, indent=2))
    for f in report["facts"]:
        print(f"{f['provider']:26} {f['fixture']:30} {f['side']}: recovered={f['recovered']}"
              f"  function_path={f['function_path_found']}")


def _span(lines) -> tuple[int, int]:
    a, _, b = str(lines).partition("-")
    return int(a), int(b or a)


# ---- setup --------------------------------------------------------------------


def pilot_check(args: argparse.Namespace) -> None:
    """Pilot on non-evaluation code (§9.5), provider-specific.

    Plumbing: every pair ran, and (CodeQL) both endpoints resolved to nodes. Plumbing
    pairs must also yield their path. Calibration pairs (CodeQL only) decide the
    `calibrate` entries of the expressibility table: a relation is expressible iff
    one line-level path covers all of the pair's expected lines. A failed calibration
    pair is a capability result, not a plumbing failure.
    """
    spec = load_spec(args.spec)
    plumbing_ok = True
    calibration: dict = {}
    for fid, fixture in spec["fixtures"].items():
        ev = json.loads((args.out / args.provider / fid / "base" / "evidence.json").read_text())
        want = [(e["file"], e["line"]) for e in fixture["expect_lines"]]
        ran = ev["status"] == "ok"
        if args.provider == "trailmark":
            resolved = ran and bool(ev.get("source_function")) and bool(ev.get("sink_function"))
            found = bool(ev.get("function_path_found"))
            ok = resolved and (found or not fixture["trailmark_must_find_path"])
        else:
            resolved = ran and ev.get("source_nodes", 0) > 0 and ev.get("sink_nodes", 0) > 0
            found = ran and any(all(any(covers(i, f, ln, ln) for i in p) for f, ln in want)
                                for p in ev.get("paths", []))
            role = fixture.get("codeql_role", "plumbing")
            if role == "info":
                ok = resolved  # reported only: its outcome is neither plumbing nor calibration
            elif role == "calibration":
                ok = resolved  # a missing path here is the calibration answer
                calibration[fixture["calibrates"]] = {"pilot": fid, "expressible": bool(found)}
            else:
                ok = resolved and found
        plumbing_ok &= ok
        print(f"{args.provider:9} {fid:24} ran={ran} endpoints_resolved={resolved} "
              f"path={found} plumbing_ok={ok}")
    if args.provider == "codeql" and plumbing_ok:
        args.calibration.parent.mkdir(parents=True, exist_ok=True)
        args.calibration.write_text(json.dumps(
            {"provider": "codeql-2.27.1-taint-path", "relations": calibration}, indent=2))
        print(f"calibration -> {args.calibration}: {calibration}")
    sys.exit(0 if plumbing_ok else 1)


def fetch_codeql(_args: argparse.Namespace) -> None:
    if CODEQL.exists():
        prov = json.loads((CODEQL_HOME / "provenance.json").read_text())
        if (prov.get("tag"), prov.get("sha256")) != (CODEQL_TAG, CODEQL_SHA256):
            sys.exit(f"installed CodeQL does not match the preregistered bundle: {prov}")
        print(f"already installed and verified: {prov['version']} ({CODEQL_TAG})")
        return
    CODEQL_HOME.mkdir(parents=True, exist_ok=True)
    archive = CODEQL_HOME / "bundle.tar.gz"
    urllib.request.urlretrieve(CODEQL_URL, archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != CODEQL_SHA256:
        archive.unlink()
        sys.exit(f"sha256 mismatch: {digest}")
    with tarfile.open(archive) as tar:
        tar.extractall(CODEQL_HOME, filter="data")
    archive.unlink()
    version = subprocess.run([str(CODEQL), "version", "--format=terse"],
                             capture_output=True, text=True, check=True).stdout.strip()
    (CODEQL_HOME / "provenance.json").write_text(json.dumps(
        {"tag": CODEQL_TAG, "sha256": digest, "version": version, "terms": CODEQL_TERMS}, indent=2))
    print(f"installed CodeQL {version} ({CODEQL_TAG}, sha256 ok)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch-codeql")
    r = sub.add_parser("run")
    r.add_argument("--provider", choices=["trailmark", "codeql"], required=True)
    r.add_argument("--spec", type=Path, default=HERE / "endpoints.yaml")
    r.add_argument("--out", type=Path, default=OUT)
    s = sub.add_parser("score")
    s.add_argument("--spec", type=Path, default=HERE / "endpoints.yaml")
    s.add_argument("--out", type=Path, default=OUT)
    s.add_argument("--report", type=Path, default=ROOT / "results" / "spike-p-reach.json")
    s.add_argument("--calibration", type=Path, default=CALIBRATION)
    c = sub.add_parser("pilot-check")
    c.add_argument("--provider", choices=["trailmark", "codeql"], required=True)
    c.add_argument("--spec", type=Path, default=HERE / "pilot.yaml")
    c.add_argument("--out", type=Path, default=ROOT / "runs" / "provider_reach_pilot")
    c.add_argument("--calibration", type=Path, default=CALIBRATION)
    args = ap.parse_args()
    {"fetch-codeql": fetch_codeql, "run": run, "score": score, "pilot-check": pilot_check}[
        args.command
    ](args)


if __name__ == "__main__":
    main()
