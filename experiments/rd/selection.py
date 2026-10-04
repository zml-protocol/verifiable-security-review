"""RD fixture selection (PREREGISTRATION.md §15.2; §15.10 step 3). DRAFT for review: not run.

    uv run python experiments/rd/selection.py pool                  # once: the ordered candidate pool
    uv run python experiments/rd/selection.py screen --language go  # the next candidate: diff checks
    uv run python experiments/rd/selection.py decide --id ID --verdict ACCEPTED --route TEST --evidence ...
    uv run python experiments/rd/selection.py decide --id ID --verdict EXEC_TRUTH_UNAVAILABLE --evidence ...
    uv run python experiments/rd/selection.py queue                 # once both queues are full: freeze

Order of work, each step logged before the next one starts:
1. `pool`: the only code that opens the OSV snapshot (open_snapshot) first requires the
   conformance gate (conformance.gate_ready()) and a snapshot copy that matches its manifest.
   Advisory-level mechanical filters, deduplication, then one seeded shuffle per language. The
   ordered pool (results/rd-candidate-pool.json) is written once, before any repository is fetched.
2. `screen`: the next undecided candidate of a language queue, strictly in pool order: fetch the
   fix commit and its parent (no checkout of the code) and apply the diff-level mechanical
   filters. Deterministic per candidate, so running them lazily in order equals running them first.
   A fetch the server answers with "does not exist" (UNAVAILABLE_PATTERNS) is COMMIT_UNAVAILABLE, a
   property of the candidate (§15.2: no locatable fix commit). Any other fetch failure is
   infrastructure: the candidate stays pending and is retried, at most FETCH_ATTEMPTS times; after
   that the selection halts (INCONCLUSIVE_INFRA) instead of moving to the next candidate. A fix
   commit with other than exactly one parent (a merge or a root) is NOT_SINGLE_PARENT.
3. `decide`: the manual admissibility checks (§15.2 item 4), recorded with a verdict from the
   frozen enumeration MANUAL. An unknown verdict stops: no category is added mid-selection.
4. `queue`: in pool order, the accepted candidates enter their language's queue unless their
   repository is already queued (either language) or any of their CWE classes already has 2
   queued fixtures (a candidate takes a place in every class it belongs to); the first 4 per
   language are primary, the next 2 reserve. The languages take turns position by position, and
   the language that goes first at odd positions is drawn from the seed. Written once.
After `pool`, every command first checks that this script and the pool file are unchanged
(SELECTION_PROTOCOL_CHANGED otherwise; there is no way to continue).
Every step appends to results/rd-selection-log.jsonl, a hash-chained append-only log.

Never used to select or reject: provider support (the vocabulary tables are not read here), how
easy or hard an advisory looks, anything learned beyond the review boundary. No fixture-specific
truth is written before the queue is frozen.

Review boundary (manual checks): only the advisory, the fix diff, the tests it touches and the
build files may be read. Executable truth is tried in this order and the route recorded: TEST (a
regression test in the fix commit: it passes at the fixed revision and fails at the parent with
the test applied), POC (a proof of concept linked from the advisory), PROBE (built from the advisory
and the fix diff alone, within 60 minutes). If a criterion cannot be decided inside the boundary,
the verdict is REVIEW_BOUNDARY_REACHED (a rejection), and the analysis stops there.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import random
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = ROOT / "results"
CACHE = ROOT / ".cache" / "rd" / "candidates"
POOL = RESULTS / "rd-candidate-pool.json"
LOG = RESULTS / "rd-selection-log.jsonl"
QUEUE = RESULTS / "rd-queue.yaml"
sys.path.insert(0, str(HERE))

import conformance
import osv_verify

SEED = 20261002
WINDOW = ("2026-01-01T00:00:00Z", "2026-09-30T00:00:00Z")
ECOSYSTEMS = {"Go": "go", "PyPI": "python"}
RETIRED = {"authlib", "caddy", "filebrowser"}
MAX_DIFF_LINES = 200
PRIMARY, RESERVE = 4, 2
PER_CLASS = 2

COMMIT_URLS = (re.compile(r"^https://(github\.com)/([\w.-]+/[\w.-]+)/commit/([0-9a-f]{40})/?$"),
               re.compile(r"^https://(gitlab\.com)/((?:[\w.-]+/)+[\w.-]+)/-/commit/([0-9a-f]{40})/?$"))
FETCH_ATTEMPTS = 3
# git's answers meaning "the server says this does not exist": a property of the candidate
UNAVAILABLE_PATTERNS = ("not our ref", "repository not found", "couldn't find remote ref",
                        "upload-pack: not our ref")
# Anything else, including an unlisted permanent-looking error, is infrastructure: the list is not
# extended during selection (a halt is preferred to a rejection rule widened after seeing candidates).
TEST_PATH = re.compile(r"(^|/)(tests?|testdata|testing)/|_test\.go$|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")
VENDOR_PATH = re.compile(r"(^|/)(vendor|third_party|_vendor)/")
SOURCE = {"go": re.compile(r"\.go$"), "python": re.compile(r"\.py$")}
DEPENDENCY_FILES = re.compile(r"(^|/)(go\.mod|go\.sum|requirements[^/]*\.txt|pyproject\.toml|setup\.cfg|"
                              r"Pipfile(\.lock)?|poetry\.lock|uv\.lock)$")

# Frozen CWE classes (§15.2 item 4: at most 2 queued fixtures per class). Unlisted CWEs are their
# own class; an advisory without a CWE is class "none".
CWE_CLASSES = {
    "path-traversal": [22, 23, 24, 35, 36, 73],
    "link-following": [59, 61],
    "injection": [74, 77, 78, 88, 89, 90, 91, 94, 95, 917, 1336],
    "xss": [79, 80, 83, 87],
    "access-control": [284, 285, 639, 862, 863, 732, 269],
    "authentication": [287, 288, 290, 294, 306, 307, 384, 613, 620, 640],
    "ssrf": [918],
    "deserialization": [502],
    "open-redirect": [601],
    "resource-consumption": [400, 405, 407, 674, 770, 789, 834, 835, 1333],
    "cryptography": [295, 297, 310, 326, 327, 328, 330, 338, 345, 347, 354],
    "information-exposure": [200, 201, 209, 212, 532, 538],
    "memory-and-bounds": [119, 120, 125, 129, 131, 190, 191, 787],
    "xml": [611, 776, 827],
    "csrf": [352],
    "input-validation": [20, 1284, 1285, 1286, 1287, 1288, 1289],
}
CWE_CLASS_OF = {cwe: cls for cls, ids in CWE_CLASSES.items() for cwe in ids}

# Diff-level mechanical outcomes (`screen`) and manual verdicts (`decide`): frozen enumerations.
MECHANICAL = ("PASS", "COMMIT_UNAVAILABLE", "NOT_SINGLE_PARENT", "NO_LANGUAGE_SOURCE_CHANGE",
              "DIFF_TOO_LARGE")  # FETCH_FAILED is an infrastructure state, never an outcome
MANUAL = {
    "ACCEPTED": "every manual criterion holds; route and evidence recorded",
    "EXEC_TRUTH_UNAVAILABLE": "no regression test, PoC or probe within the boundary and the time box",
    "EXEC_TRUTH_NOT_CONFIRMED": "the test/PoC/probe ran, but the parent does not show the effect or the fix still does",
    "BUILD_UNAVAILABLE": "does not build or run locally, or needs an external commercial service or special hardware",
    "VENDORED_CODE": "the vulnerable code is in a vendored dependency, not the repository's own code",
    "REVIEW_BOUNDARY_REACHED": "a criterion cannot be decided from the advisory, the fix diff, its tests and the build files",
}
ROUTES = ("TEST", "POC", "PROBE")


# ---- the snapshot: one gated entry point --------------------------------------------------------


def open_snapshot() -> list[dict]:
    """The only reader of the OSV snapshot: refuses unless the conformance gate is READY and the
    local copy matches its manifest."""
    if not conformance.gate_ready():
        sys.exit("the conformance gate is not READY: the OSV snapshot stays closed")
    manifest = json.loads(osv_verify.MANIFEST.read_text())
    directory = ROOT / manifest["local_dir"]
    if problems := osv_verify.problems(directory):
        sys.exit("snapshot copy does not match its manifest: " + "; ".join(problems))
    records = []
    for eco, entry in manifest["files"].items():
        with zipfile.ZipFile(directory / entry["file"]) as z:
            for name in sorted(z.namelist()):
                if name.endswith(".json"):
                    records.append({"_ecosystem_file": eco, **json.loads(z.read(name))})
    return records


# ---- advisory-level mechanical filters ------------------------------------------------------------


def fix_commits(rec: dict) -> set[tuple[str, str]]:
    """(repository URL, commit) pairs the advisory points to: commit URLs among its references, and
    `fixed` events of GIT ranges."""
    out = set()
    for ref in rec.get("references") or []:
        for pattern in COMMIT_URLS:
            if m := pattern.match(ref.get("url", "")):
                host, path, sha = m.groups()
                out.add((f"https://{host}/{path.removesuffix('.git')}".lower(), sha))
    for aff in rec.get("affected") or []:
        for rng in aff.get("ranges") or []:
            if rng.get("type") == "GIT" and rng.get("repo"):
                for ev in rng.get("events") or []:
                    if re.fullmatch(r"[0-9a-f]{40}", ev.get("fixed", "")):
                        out.add((rng["repo"].lower().removesuffix(".git").rstrip("/"), ev["fixed"]))
    return out


def cwe_ids(rec: dict) -> list[int]:
    ids = (rec.get("database_specific") or {}).get("cwe_ids") or []
    return sorted({int(m.group(1)) for c in ids if (m := re.fullmatch(r"CWE-(\d+)", str(c)))})


def cwe_classes(ids: list[int]) -> list[str]:
    """Every class the advisory's CWEs belong to (an unlisted CWE is its own class); ["none"]
    without a CWE. A candidate takes a quota place in each."""
    return sorted({CWE_CLASS_OF.get(i, f"CWE-{i}") for i in ids}) or ["none"]


def advisory_filter(rec: dict) -> tuple[str, dict | None]:
    """(reason, candidate): reason is "PASS" or the first filter that rejects it."""
    language = ECOSYSTEMS.get(rec["_ecosystem_file"])
    if language is None:
        return "WRONG_ECOSYSTEM", None
    if rec.get("withdrawn"):
        return "WITHDRAWN", None
    published = rec.get("published") or ""
    if not (WINDOW[0] <= published < WINDOW[1]):
        return "OUT_OF_WINDOW", None
    commits = fix_commits(rec)
    if not commits:
        return "NO_FIX_COMMIT", None
    if len(commits) > 1:
        return "MULTIPLE_FIX_COMMITS", None
    repo, sha = next(iter(commits))
    if repo.rsplit("/", 1)[-1] in RETIRED:
        return "RETIRED_REPOSITORY", None
    ids = cwe_ids(rec)
    return "PASS", {"id": rec["id"], "aliases": sorted(rec.get("aliases") or []), "language": language,
                    "listed_in": {rec["id"]: language},
                    "published": published, "repo": repo, "fix_commit": sha, "cwe_ids": ids,
                    "cwe_classes": cwe_classes(ids)}


def build_pool(records: list[dict]) -> dict:
    counts: dict[str, int] = {}
    passed = []
    for rec in records:
        reason, cand = advisory_filter(rec)
        counts[reason] = counts.get(reason, 0) + 1
        if cand:
            passed.append(cand)
    # one candidate per (repository, fix commit): GO-, GHSA- and PYSEC- aliases of one fix
    by_commit: dict[tuple[str, str], dict] = {}
    for c in sorted(passed, key=lambda c: (c["published"], c["id"])):
        key = (c["repo"], c["fix_commit"])
        if key in by_commit:
            kept = by_commit[key]  # the earliest published id stays; aliases' metadata is merged
            kept.setdefault("duplicates", []).append(c["id"])
            kept["aliases"] = sorted(set(kept["aliases"]) | set(c["aliases"]) | {c["id"]})
            kept["cwe_ids"] = sorted(set(kept["cwe_ids"]) | set(c["cwe_ids"]))
            kept["cwe_classes"] = cwe_classes(kept["cwe_ids"])
            kept["listed_in"] = {**kept["listed_in"], **c["listed_in"]}  # which ecosystem listed each alias
        else:
            by_commit[key] = c
    counts["DUPLICATE_FIX_COMMIT"] = len(passed) - len(by_commit)
    queues = {}
    for language in sorted(set(ECOSYSTEMS.values())):
        cands = sorted((c for c in by_commit.values() if c["language"] == language), key=lambda c: c["id"])
        random.Random(f"{SEED}:{language}").shuffle(cands)
        queues[language] = [{**c, "position": i} for i, c in enumerate(cands, 1)]
    return {"seed": SEED, "window": WINDOW, "records": len(records), "filter_counts": counts,
            "parameters": {"retired": sorted(RETIRED), "max_diff_lines": MAX_DIFF_LINES,
                           "primary": PRIMARY, "reserve": RESERVE, "per_cwe_class": PER_CLASS,
                           "cwe_classes": CWE_CLASSES},
            "queues": queues}


# ---- the hash-chained log -------------------------------------------------------------------------


def log_entries() -> list[dict]:
    return [json.loads(line) for line in LOG.read_text().splitlines()] if LOG.exists() else []


def append_log(entry: dict) -> dict:
    entries = log_entries()
    prev = entries[-1]["hash"] if entries else "0" * 64
    body = {**entry, "at_utc": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
            "prev": prev}
    body["hash"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    with LOG.open("a") as f:
        f.write(json.dumps(body, sort_keys=True) + "\n")
    return body


def chain_problems(entries: list[dict]) -> list[str]:
    prev, out = "0" * 64, []
    for i, e in enumerate(entries):
        body = {k: v for k, v in e.items() if k != "hash"}
        if e.get("prev") != prev or hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() != e.get("hash"):
            out.append(f"log entry {i + 1} breaks the chain")
        prev = e.get("hash")
    return out


# ---- after `pool`: the same script, the same pool ------------------------------------------------


def script_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def protocol_problems(pool_doc: dict, pool_bytes: bytes, entries: list[dict]) -> list[str]:
    out = chain_problems(entries)
    if pool_doc.get("script_sha256") != script_sha256():
        out.append("selection.py differs from the script that wrote the pool")
    pool_entries = [e for e in entries if e.get("step") == "pool"]
    if len(pool_entries) != 1 or pool_entries[0].get("pool_sha256") != hashlib.sha256(pool_bytes).hexdigest():
        out.append("the candidate pool differs from the one logged by `pool`")
    return out


def checked() -> tuple[dict, list[dict]]:
    """Every command after `pool` starts here: SELECTION_PROTOCOL_CHANGED stops it for good."""
    pool_bytes = POOL.read_bytes()
    pool_doc, entries = json.loads(pool_bytes), log_entries()
    if p := protocol_problems(pool_doc, pool_bytes, entries):
        sys.exit("SELECTION_PROTOCOL_CHANGED: " + "; ".join(p))
    return pool_doc, entries


# ---- screening: strictly in pool order ------------------------------------------------------------


def state(entries: list[dict]) -> dict[str, dict]:
    """Per candidate id: its mechanical outcome, manual verdict and failed fetch attempts so far."""
    out: dict[str, dict] = {}
    for e in entries:
        if e["step"] in ("screen", "decide"):
            out.setdefault(e["id"], {})[e["step"]] = e
        elif e["step"] == "fetch_failed":
            s = out.setdefault(e["id"], {})
            s["fetch_failures"] = s.get("fetch_failures", 0) + 1
    return out


def halted(entries: list[dict]) -> list[str]:
    """Candidates whose fetch failed FETCH_ATTEMPTS times: the selection is INCONCLUSIVE_INFRA."""
    return sorted(i for i, s in state(entries).items() if s.get("fetch_failures", 0) >= FETCH_ATTEMPTS
                  and "screen" not in s)


def next_candidate(pool: dict, language: str, entries: list[dict]) -> dict | None:
    """The first candidate of the language queue not yet finished. A candidate is finished when its
    mechanical outcome is not PASS, or it has a manual verdict."""
    st = state(entries)
    for c in pool["queues"][language]:
        s = st.get(c["id"], {})
        if "screen" in s and s["screen"]["outcome"] != "PASS":
            continue
        if "decide" in s:
            continue
        return c
    return None


def diff_outcome(numstat: list[tuple[int, int, str]], language: str) -> tuple[str, dict]:
    non_test = [(a, d, p) for a, d, p in numstat if not TEST_PATH.search(p)]
    source = [p for _, _, p in non_test if SOURCE[language].search(p) and not DEPENDENCY_FILES.search(p)]
    lines = sum(a + d for a, d, _ in non_test)
    facts = {"files": len(numstat), "non_test_lines": lines, "source_files": source,
             "vendored_only": bool(source) and all(VENDOR_PATH.search(p) for p in source),
             "test_files": sorted(p for _, _, p in numstat if TEST_PATH.search(p))}
    if not source:
        return "NO_LANGUAGE_SOURCE_CHANGE", facts
    if lines > MAX_DIFF_LINES:
        return "DIFF_TOO_LARGE", facts
    return "PASS", facts


def classify_fetch_error(stderr: str) -> str:
    """COMMIT_UNAVAILABLE when the server says the repository or commit does not exist, else
    FETCH_FAILED (infrastructure)."""
    text = stderr.lower()
    return "COMMIT_UNAVAILABLE" if any(p in text for p in UNAVAILABLE_PATTERNS) else "FETCH_FAILED"


def fetch_numstat(cand: dict) -> tuple[str, list[tuple[int, int, str]] | str]:
    """("OK", numstat rows) for a single-parent fix commit fetched with its parent and no checkout;
    otherwise (COMMIT_UNAVAILABLE | NOT_SINGLE_PARENT | FETCH_FAILED, git's message)."""
    repo = CACHE / cand["id"]
    repo.mkdir(parents=True, exist_ok=True)

    def git(*a):
        try:
            return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, timeout=900,
                                  check=False)
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(a, 124, "", "timeout")
    if not (repo / ".git").exists() and (r := git("init", "-q")).returncode != 0:
        return "FETCH_FAILED", r.stderr
    if (r := git("fetch", "-q", "--depth=2", cand["repo"], cand["fix_commit"])).returncode != 0:
        return classify_fetch_error(r.stderr), r.stderr[-500:]
    parents = git("rev-list", "--parents", "-n", "1", cand["fix_commit"]).stdout.split()[1:]
    if len(parents) != 1:
        return "NOT_SINGLE_PARENT", f"{len(parents)} parents"
    out = git("diff", "--numstat", parents[0], cand["fix_commit"])
    if out.returncode != 0:
        return "FETCH_FAILED", out.stderr[-500:]
    rows = []
    for line in out.stdout.splitlines():
        a, d, p = line.split("\t", 2)
        rows.append((int(a) if a.isdigit() else 0, int(d) if d.isdigit() else 0, p))
    return "OK", rows


def screen(args: argparse.Namespace) -> None:
    pool, entries = checked()
    if stuck := halted(entries):
        sys.exit(f"INCONCLUSIVE_INFRA: fetching {stuck} failed {FETCH_ATTEMPTS} times; the selection halts")
    cand = next_candidate(pool, args.language, entries)
    if cand is None:
        sys.exit(f"{args.language}: the pool is exhausted")
    if "screen" in state(entries).get(cand["id"], {}):
        print(f"{cand['id']} passed the diff checks; awaiting `decide`")
        return
    status, payload = fetch_numstat(cand)
    if status == "FETCH_FAILED":
        append_log({"step": "fetch_failed", "id": cand["id"], "language": args.language, "message": payload})
        sys.exit(f"{cand['id']}: fetch failed (infrastructure); the candidate stays pending")
    if status == "OK":
        outcome, facts = diff_outcome(payload, args.language)
    else:
        outcome, facts = status, {"message": payload}
    append_log({"step": "screen", "id": cand["id"], "language": args.language,
                "position": cand["position"], "outcome": outcome, "facts": facts})
    print(json.dumps({"id": cand["id"], "position": cand["position"], "outcome": outcome, **facts}, indent=1))


def decide(args: argparse.Namespace) -> None:
    if args.verdict not in MANUAL:
        sys.exit(f"unknown verdict {args.verdict!r}: the enumeration is frozen; stop and report instead")
    if args.verdict == "ACCEPTED" and args.route not in ROUTES:
        sys.exit(f"an accepted candidate needs --route in {ROUTES}")
    if not args.evidence.strip():
        sys.exit("--evidence is required")
    pool, entries = checked()
    lang = next((lang for lang, q in pool["queues"].items() if any(c["id"] == args.id for c in q)), None)
    if lang is None:
        sys.exit(f"{args.id} is not in the candidate pool")
    cand = next_candidate(pool, lang, entries)
    if cand is None or cand["id"] != args.id:
        sys.exit(f"{args.id} is not the next candidate of the {lang} queue ({cand and cand['id']})")
    if state(entries).get(args.id, {}).get("screen", {}).get("outcome") != "PASS":
        sys.exit(f"{args.id} has not passed the diff checks")
    append_log({"step": "decide", "id": args.id, "language": lang, "position": cand["position"],
                "verdict": args.verdict, "route": args.route if args.verdict == "ACCEPTED" else None,
                "evidence": args.evidence})


# ---- the queue ------------------------------------------------------------------------------------


def turn_order(languages: list[str], position: int) -> list[str]:
    """Who picks first at a position: a seeded draw for odd positions, the other language for even
    ones (position counted from 1), so neither language always gets first pick of the quotas."""
    first = random.Random(f"{SEED}:first").choice(sorted(languages))
    rest = [lang for lang in sorted(languages) if lang != first]
    return [first, *rest] if position % 2 == 1 else [*rest, first]


def build_queue(pool: dict, entries: list[dict]) -> tuple[dict, list[dict]]:
    """In pool order per language, the languages taking turns: accepted candidates enter unless their
    repository is queued already or any of their CWE classes is full; first PRIMARY are primary,
    next RESERVE reserve."""
    st = state(entries)
    queues = {lang: [] for lang in pool["queues"]}
    skipped = []
    repos, classes = set(), {}
    longest = max(len(q) for q in pool["queues"].values())
    for i in range(longest):
        for lang in turn_order(list(pool["queues"]), i + 1):
            q = pool["queues"][lang]
            if i >= len(q) or len(queues[lang]) >= PRIMARY + RESERVE:
                continue
            c = q[i]
            if st.get(c["id"], {}).get("decide", {}).get("verdict") != "ACCEPTED":
                continue
            if c["repo"] in repos:
                skipped.append({"id": c["id"], "reason": "DUPLICATE_REPOSITORY"})
                continue
            if full := [k for k in c["cwe_classes"] if classes.get(k, 0) >= PER_CLASS]:
                skipped.append({"id": c["id"], "reason": "CWE_CLASS_QUOTA", "classes": full})
                continue
            repos.add(c["repo"])
            for k in c["cwe_classes"]:
                classes[k] = classes.get(k, 0) + 1
            role = "primary" if len(queues[lang]) < PRIMARY else "reserve"
            queues[lang].append({"id": c["id"], "role": role, "position": c["position"], "repo": c["repo"],
                                 "fix_commit": c["fix_commit"], "cwe_classes": c["cwe_classes"]})
    return queues, skipped


def queue(_args: argparse.Namespace) -> None:
    if QUEUE.exists():
        sys.exit("the queue is frozen")
    pool, entries = checked()
    if stuck := halted(entries):
        sys.exit(f"INCONCLUSIVE_INFRA: fetching {stuck} failed {FETCH_ATTEMPTS} times")
    queues, skipped = build_queue(pool, entries)
    for lang, q in queues.items():
        if len(q) < PRIMARY + RESERVE and next_candidate(pool, lang, entries) is not None:
            sys.exit(f"{lang}: {len(q)} queued and candidates remain undecided: keep screening")
    doc = {"seed": SEED, "pool_sha256": hashlib.sha256(POOL.read_bytes()).hexdigest(),
           "log_head": entries[-1]["hash"] if entries else None, "queues": queues, "skipped": skipped,
           "n": {lang: len(q) for lang, q in queues.items()}}
    QUEUE.write_text(yaml.safe_dump(doc, sort_keys=False))
    append_log({"step": "queue", "queue_sha256": hashlib.sha256(QUEUE.read_bytes()).hexdigest(),
                "n": doc["n"]})


def status(_args: argparse.Namespace) -> None:
    """How full the queues would be now (nothing is frozen): screening stops for a language when
    its queue holds PRIMARY + RESERVE."""
    pool_doc, entries = checked()
    queues, skipped = build_queue(pool_doc, entries)
    if stuck := halted(entries):
        print(f"INCONCLUSIVE_INFRA: {stuck}")
    print(json.dumps({lang: [f"{c['id']} ({c['role']})" for c in q] for lang, q in queues.items()}, indent=1))
    print("skipped:", skipped)


def pool(_args: argparse.Namespace) -> None:
    if POOL.exists():
        sys.exit("the candidate pool is written once")
    doc = build_pool(open_snapshot())
    manifest = json.loads(osv_verify.MANIFEST.read_text())
    doc["snapshot"] = {eco: e["sha256"] for eco, e in manifest["files"].items()}
    doc["script_sha256"] = script_sha256()
    POOL.write_text(json.dumps(doc, indent=1) + "\n")
    append_log({"step": "pool", "pool_sha256": hashlib.sha256(POOL.read_bytes()).hexdigest(),
                "filter_counts": doc["filter_counts"], "sizes": {k: len(v) for k, v in doc["queues"].items()}})
    print(json.dumps({"filter_counts": doc["filter_counts"],
                      "sizes": {k: len(v) for k, v in doc["queues"].items()}}, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pool")
    s = sub.add_parser("screen")
    s.add_argument("--language", choices=sorted(set(ECOSYSTEMS.values())), required=True)
    d = sub.add_parser("decide")
    d.add_argument("--id", required=True)
    d.add_argument("--verdict", required=True)
    d.add_argument("--route", choices=ROUTES)
    d.add_argument("--evidence", required=True)
    sub.add_parser("queue")
    sub.add_parser("status")
    args = ap.parse_args()
    {"pool": pool, "screen": screen, "decide": decide, "queue": queue, "status": status}[args.cmd](args)


if __name__ == "__main__":
    main()
