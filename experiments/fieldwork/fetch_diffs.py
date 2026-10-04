"""Fetch the fix-commit diffs of one candidate repo, for personal fix-completeness analysis.

    uv run python experiments/fieldwork/fetch_diffs.py open-webui/open-webui

Uses the GitHub commits API (patch text only) so nothing is cloned yet. Output:
.cache/fieldwork/diffs/<owner__repo>/<id>.json  with the commit message, stats, and per-file patches.
A heuristic screen score highlights patches that add validation/normalization logic, where an
incomplete fix (a missed path, encoding, or alias) is most plausible.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache" / "fieldwork" / "diffs"

# Lines that usually mean "the fix added a decision point", i.e. a place a bypass would target.
DECISION = re.compile(
    r"\b(if|elif|return|raise|continue|assert)\b.*\b("
    r"check|valid|sanitiz|allow|deny|permit|forbid|blocklist|blacklist|whitelist|clean|normal|"
    r"escape|quote|replace|strip|startswith|endswith|isfile|isdir|exists|resolve|realpath|abspath|"
    r"relative_to|urlparse|urllib|ip_address|is_private|is_loopback|is_global|socket|hostname|"
    r"authoriz|permission|admin|role|token|secret|session|password|user_id|owner|trusted|"
    r"header|cookie|origin|referer|redirect|scheme|netloc|path|filename|template|selector|"
    r"size|limit|length|max|min|timeout"
    r")\b", re.IGNORECASE)
TEST_HINT = re.compile(r"(^|/)(tests?|testdata)/|_test\.go$|(^|/)test_[^/]*\.py$|_test\.py$")


def candidates(slug: str) -> list[dict]:
    pool = json.loads((ROOT / "results" / "rd-candidate-pool.json").read_text())
    out = []
    for lang, queue in pool["queues"].items():
        for c in queue:
            if c["repo"] == f"https://github.com/{slug}":
                out.append({**c, "language": lang})
    return sorted(out, key=lambda c: c["position"])


def fetch_one(slug: str, cand: dict, out_dir: Path) -> dict | None:
    path = out_dir / f"{cand['id']}.json"
    if path.exists():
        return json.loads(path.read_text())
    proc = subprocess.run(["gh", "api", f"repos/{slug}/commits/{cand['fix_commit']}"],
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        print(f"  {cand['id']}: API error: {proc.stderr.strip()[:120]}", file=sys.stderr)
        return None
    raw = json.loads(proc.stdout)
    doc = {
        "id": cand["id"], "sha": cand["fix_commit"], "language": cand["language"],
        "cwe_ids": cand["cwe_ids"], "cwe_classes": cand["cwe_classes"],
        "message": raw.get("commit", {}).get("message", ""),
        "files": [{"filename": f["filename"], "status": f["status"],
                   "additions": f.get("additions"), "deletions": f.get("deletions"),
                   "patch": f.get("patch", "")} for f in raw.get("files", [])],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def score(doc: dict) -> dict:
    added = [l for f in doc["files"] for l in f["patch"].splitlines() if l.startswith("+") and not l.startswith("+++")]
    decision = sum(1 for l in added if DECISION.search(l))
    tests = [f["filename"] for f in doc["files"] if TEST_HINT.search(f["filename"])]
    source = [f["filename"] for f in doc["files"] if not TEST_HINT.search(f["filename"])]
    return {"decision_lines": decision, "added": len(added),
            "source_files": len(source), "test_files": len(tests), "files": len(doc["files"])}


def main() -> None:
    slug = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    cands = candidates(slug)
    if not cands:
        sys.exit(f"{slug}: not in the candidate pool")
    out_dir = CACHE / slug.replace("/", "__")
    docs = []
    for i, c in enumerate(cands, 1):
        if limit and i > limit:
            break
        d = fetch_one(slug, c, out_dir)
        if d:
            docs.append((c, d))
        print(f"  {i}/{len(cands)} {c['id']}", file=sys.stderr)
    rows = []
    for c, d in docs:
        s = score(d)
        head = d["message"].splitlines()[0][:72]
        rows.append((s["decision_lines"], s["added"], s["test_files"], c, d, s, head))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    print(f"\n{'dec':>3} {'add':>4} {'tst':>3}  {'id':<22} {'classes':<40} message")
    for dec, add, tst, c, d, s, head in rows:
        print(f"{dec:>3} {add:>4} {tst:>3}  {c['id']:<22} {','.join(c['cwe_classes'])[:38]:<40} {head}")


if __name__ == "__main__":
    main()
