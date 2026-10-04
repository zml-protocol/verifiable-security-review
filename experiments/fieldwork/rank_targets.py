"""Rank the RD candidate repos for personal fieldwork (fix-completeness analysis).

This is NOT part of the frozen RD protocol: it reads only the public candidate pool
(results/rd-candidate-pool.json) and GitHub metadata, and writes nothing under results/ or
runs/. Its output feeds `runs/fieldwork/` target notes.

    uv run python experiments/fieldwork/rank_targets.py fetch   # stars/archived -> .cache/fieldwork
    uv run python experiments/fieldwork/rank_targets.py list    # ranked shortlist

No repository content is read here; only metadata (stars, archived, pushedAt, language).
"""

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache" / "fieldwork"
META = CACHE / "github_meta.json"
BATCH = 40

# CWE classes worth touching for an AppSec portfolio: reachable, input-driven, web-adjacent.
INTERESTING = {
    "path-traversal", "injection", "ssrf", "access-control", "authentication", "deserialization",
    "open-redirect", "xss", "csrf", "information-exposure", "link-following", "input-validation",
    "cryptography", "xml", "CWE-434", "CWE-502", "CWE-918", "CWE-22", "CWE-89", "CWE-78",
}

# Giant monorepos where a quick local probe is not realistic.
EXCLUDE_REPOS = {
    "tensorflow/tensorflow", "apache/airflow", "django/django", "pytorch/pytorch",
    "python/cpython", "golang/go", "torvalds/linux", "kubernetes/kubernetes",
}


def repos_from_pool() -> dict[str, dict]:
    pool = json.loads((ROOT / "results" / "rd-candidate-pool.json").read_text())
    out: dict[str, dict] = {}
    for lang, queue in pool["queues"].items():
        for c in queue:
            url = c["repo"]
            if not url.startswith("https://github.com/"):
                continue
            slug = url[len("https://github.com/"):].removesuffix(".git").strip("/")
            if "/" not in slug:
                continue
            entry = out.setdefault(slug, {"slug": slug, "ids": [], "classes": set(), "languages": set()})
            entry["ids"].append(c["id"])
            entry["classes"].update(c["cwe_classes"])
            entry["languages"].add(lang)
    for e in out.values():
        e["classes"] = sorted(e["classes"])
        e["languages"] = sorted(e["languages"])
    return out


def rest_one(slug: str) -> tuple[str, dict]:
    proc = subprocess.run(
        ["gh", "api", f"repos/{slug}", "--jq",
         "{stars: .stargazers_count, archived: .archived, pushed_at: .pushed_at, language: .language}"],
        capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        return slug, {"missing": True}
    try:
        return slug, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return slug, {"missing": True}


def fetch() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    repos = repos_from_pool()
    slugs = sorted(repos)
    print(f"{len(slugs)} GitHub repos", file=sys.stderr)
    meta: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=16) as pool:
        for i, (slug, m) in enumerate(pool.map(rest_one, slugs)):
            meta[slug] = m
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(slugs)}", file=sys.stderr)
    META.write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n")
    missing = sum(1 for m in meta.values() if m.get("missing"))
    print(f"wrote {META}: {len(meta)} repos, {missing} missing", file=sys.stderr)


def list_targets() -> None:
    repos = repos_from_pool()
    meta = json.loads(META.read_text()) if META.exists() else {}
    rows = []
    for slug, e in repos.items():
        m = meta.get(slug, {})
        if m.get("missing") or m.get("archived"):
            continue
        if slug in EXCLUDE_REPOS:
            continue
        stars = m.get("stars", 0)
        interesting = [c for c in e["classes"] if c in INTERESTING]
        if stars < 300 or not interesting:
            continue
        rows.append({**e, "stars": stars, "pushed_at": m.get("pushed_at"),
                     "github_language": m.get("language"), "interesting": interesting,
                     "n_candidates": len(e["ids"])})
    rows.sort(key=lambda r: (-r["stars"], r["slug"]))
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "ranked.json").write_text(json.dumps(rows, indent=1) + "\n")
    print(f"{'stars':>7}  {'n':>2}  repo                                  classes")
    for r in rows[:80]:
        print(f"{r['stars']:>7}  {r['n_candidates']:>2}  {r['slug']:<38} {','.join(r['interesting'])}")
    print(f"\n{len(rows)} repos pass the filter; full list in {CACHE / 'ranked.json'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    {"fetch": fetch, "list": list_targets}[cmd]()
