"""Mechanical pre-check for RD manual admissibility (fieldwork tool, not part of §15).

    uv run python experiments/fieldwork/rd_precheck.py <candidate-id> [<candidate-id> ...]

For each candidate it reads, without network and without writing outside runs/rd/precheck:

- the frozen OSV snapshot copy (identifier/alias/summary-level data only),
- the candidate's cached bare repo under .cache/rd/candidates/<id>/,

and produces facts only:

- the fix commit's file list (test vs non-test, added/deleted lines),
- whether the fix commit touches any test file,
- which identifiers named in the advisory text also appear in those test files,
- the test files' paths and sizes at the fix commit.

It reads the snapshot only through the frozen selection entry points: ``selection.checked()``
verifies the script hash, pool hash and log chain, and ``selection.open_snapshot()`` runs the
conformance gate and the manifest check. No second, ungated advisory reader.

It never reads product source beyond the fix diff, never decides a verdict, and never appends to
results/rd-selection-log.jsonl. The manual checker still reads the advisory and the diff,
reproduces the behaviour, and runs `decide`.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POOL = ROOT / "results" / "rd-candidate-pool.json"
OUT = ROOT / "runs" / "rd" / "precheck"
RD = ROOT / "experiments" / "rd"
if str(RD) not in sys.path:
    sys.path.insert(0, str(RD))

_checked = False

# Mirrors selection.py's screen classification (do not edit selection.py).
TEST_PATH = re.compile(r"(^|/)(tests?|testdata|testing)/|_test\.go$|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")
DEPENDENCY_FILES = re.compile(
    r"(^|/)(go\.mod|go\.sum|requirements[^/]*\.txt|pyproject\.toml|setup\.cfg|Pipfile(\.lock)?|poetry\.lock|uv\.lock)$"
)
CODE_SPAN = re.compile(r"`([^`\n]{2,80})`")
SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
STOP = {
    "true", "false", "none", "null", "http", "https", "json", "api", "url", "uri", "get", "post",
    "put", "patch", "delete", "if", "else", "return", "and", "or", "not", "in", "is", "as",
    "for", "def", "class", "self", "str", "int", "dict", "list", "bool", "set", "file", "path",
}


def ensure_checked() -> None:
    """The provenance gate: script hash vs pool, pool hash vs log, log chain. Runs before any
    candidate is read from the pool and before any repository is touched."""
    global _checked
    if _checked:
        return
    try:
        from selection import checked
    except Exception as exc:  # pragma: no cover - environment problem
        raise SystemExit(
            f"cannot import the frozen selection module: {exc}. "
            "Run with `uv run python ...` from the repository root."
        ) from exc
    checked()
    _checked = True


def _selection_script_hash() -> str:
    from selection import script_sha256

    return script_sha256()


def _log_head() -> str | None:
    from selection import log_entries

    entries = log_entries()
    return entries[-1]["hash"] if entries else None


def candidate(pid: str) -> dict:
    ensure_checked()
    pool = json.loads(POOL.read_text())
    for queue in pool["queues"].values():
        for c in queue:
            if c["id"] == pid:
                return c
    sys.exit(f"{pid}: not in the candidate pool")


_snapshot_records: list[dict] | None = None


def snapshot_records() -> list[dict]:
    """The frozen snapshot, reached only through selection's gate-checked entry."""
    global _snapshot_records
    if _snapshot_records is None:
        ensure_checked()
        try:
            from selection import open_snapshot
        except Exception as exc:  # pragma: no cover - environment problem
            raise SystemExit(f"cannot import open_snapshot: {exc}") from exc
        _snapshot_records = open_snapshot()  # conformance gate + manifest-checked copy
    return _snapshot_records


def advisory_record(cand: dict) -> dict:
    return next((rec for rec in snapshot_records() if rec.get("id") == cand["id"]), {})


def identifiers(rec: dict) -> list[str]:
    text = " ".join([str(rec.get("summary") or ""), str(rec.get("details") or "")])
    found = set(CODE_SPAN.findall(text)) | set(SNAKE.findall(text))
    out = []
    for token in sorted(found):
        t = token.strip()
        if len(t) < 3 or t.lower() in STOP:
            continue
        out.append(t)
    return out


def git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[:200])
    return proc.stdout


def one(pid: str) -> dict:
    cand = candidate(pid)
    fix = cand["fix_commit"]
    repo = ROOT / ".cache" / "rd" / "candidates" / pid
    parent = git(repo, "rev-parse", f"{fix}^").strip()

    name_status = git(repo, "diff", "--name-status", parent, fix).splitlines()
    files = []
    for line in name_status:
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        status, path = parts
        try:
            numstat = git(repo, "diff", "--numstat", parent, fix, "--", path).split("\t")
            added, deleted = int(numstat[0]), int(numstat[1])
        except Exception:
            added = deleted = 0
        files.append({
            "path": path, "status": status, "added": added, "deleted": deleted,
            "test": bool(TEST_PATH.search(path)),
            "dependency": bool(DEPENDENCY_FILES.search(path)),
        })

    tests = [f for f in files if f["test"]]
    ids = identifiers(advisory_record(cand))
    hits: dict[str, list[str]] = {}
    for tf in tests:
        try:
            content = git(repo, "show", f"{fix}:{tf['path']}")
        except Exception:
            continue
        matched = [i for i in ids if i in content]
        if matched:
            hits[tf["path"]] = matched

    non_test_lines = sum(f["added"] + f["deleted"] for f in files if not f["test"] and not f["dependency"])
    facts = {
        "id": pid, "repo": cand["repo"], "fix_commit": fix, "parent": parent,
        "language": next(iter(cand["listed_in"].values())),
        "files": files,
        "facts": {
            "file_count": len(files),
            "test_file_count": len(tests),
            "non_test_non_dep_lines": non_test_lines,
            "advisory_identifier_count": len(ids),
            "test_files_with_advisory_identifiers": hits,
        },
        "provenance": {
            "script_sha256": _selection_script_hash(),
            "pool_sha256": hashlib.sha256(POOL.read_bytes()).hexdigest(),
            "log_head": _log_head(),
        },
        "note": "mechanical facts only; no admissibility verdict. The manual checker reads the "
                "advisory and the diff, reproduces the behaviour, and runs `decide`.",
    }

    out_dir = OUT / pid
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "facts.json").write_text(json.dumps(facts, indent=1) + "\n")

    lines = [
        f"# RD pre-check: {pid}", "",
        f"- repository: {cand['repo']}",
        f"- fix commit: `{fix}` (parent `{parent}`)",
        f"- changed files: {len(files)} ({len(tests)} test, "
        f"{sum(1 for f in files if f['dependency'])} dependency)",
        f"- non-test, non-dependency changed lines: {non_test_lines}",
        f"- advisory identifiers mechanically extracted: {len(ids)}",
        "",
    ]
    if tests:
        lines.append("| test file | + | - | advisory identifiers found |")
        lines.append("|---|---:|---:|---|")
        for tf in tests:
            found = ", ".join(f"`{i}`" for i in hits.get(tf["path"], [])) or "-"
            lines.append(f"| `{tf['path']}` | {tf['added']} | {tf['deleted']} | {found} |")
    else:
        lines.append("No test file is changed by the fix commit (mechanical fact).")
    lines += ["", "Files:", ""]
    lines.append("| path | status | + | - | test | dependency |")
    lines.append("|---|---|---:|---:|---|---|")
    for f in files:
        lines.append(f"| `{f['path']}` | {f['status']} | {f['added']} | {f['deleted']} | "
                     f"{'yes' if f['test'] else ''} | {'yes' if f['dependency'] else ''} |")
    lines += ["", f"_Facts only; no verdict. Manual checker still runs `decide`._", ""]
    (out_dir / "summary.md").write_text("\n".join(lines))
    return facts


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for pid in sys.argv[1:]:
        try:
            facts = one(pid)
        except Exception as exc:  # infrastructure, not a candidate property
            print(f"{pid}: precheck failed: {exc}")
            continue
        f = facts["facts"]
        print(f"{pid}: {f['file_count']} files, {f['test_file_count']} test, "
              f"{f['non_test_non_dep_lines']} non-test lines, "
              f"{len(f['test_files_with_advisory_identifiers'])} test file(s) hit advisory identifiers")
        print(f"  -> runs/rd/precheck/{pid}/summary.md")


if __name__ == "__main__":
    main()
