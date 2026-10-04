"""Build the frozen CodeQL relation analysis consumed by RD phase B.

The queries and relation semantics are reused byte-for-byte from the frozen
P-Hybrid-1, bridge and same-object components.  This wrapper only applies them
to the five fresh repositories under neutral revision labels.
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
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for directory in (ROOT / "experiments" / "hop_verify",
                  ROOT / "experiments" / "hop_chain",
                  HERE):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import connector  # noqa: E402
import verify  # noqa: E402
from spike.gitrepo import GitRepo  # noqa: E402

import session  # noqa: E402
import tasks  # noqa: E402

RUNS = ROOT / "runs" / "rd" / "agent" / "analysis"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _materialize(repo: Path, commit: str, dest: Path) -> None:
    shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="rd-src-", dir=dest.parent))
    try:
        archive = subprocess.run(["git", "-C", str(repo), "archive", commit],
                                 capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", str(tmp)], input=archive, check=True)
        tmp.rename(dest)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def _queries(language: str) -> tuple[list[Path], dict[str, Path]]:
    p1_root = ROOT / "experiments" / "hop_verify" / "queries" / language
    bridge_root = ROOT / "experiments" / "hop_bridge" / "queries" / language
    p1_doc = verify.relations()
    shapes = [p1_root / p1_doc["shapes"][language], bridge_root / "BridgeShapes.ql"]
    relations = session.relation_specs(language)
    paths = {}
    bridge_names = set(
        __import__("yaml").safe_load((ROOT / "experiments/hop_bridge/relations.yaml").read_text())
        ["relations"][language]
    )
    for name, spec in relations.items():
        paths[name] = (bridge_root if name in bridge_names else p1_root) / spec["verifier"]
    return shapes, paths


def build_spec(t: dict, task_id: str, revision: str, out_dir: Path) -> Path:
    """Analyze one task-like spec. Used by formal tasks and the synthetic pilot."""
    frozen = out_dir / "analysis.json.gz"
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    source = out_dir / "source"
    _materialize(Path(t["repo"]), t["revisions"][revision], source)
    language = t["language"]
    env = {**os.environ, **(verify.reach.go_env() if language == "go" else {})}
    db = out_dir / "db"
    create = [str(verify.reach.CODEQL), "database", "create", str(db), f"--language={language}",
              f"--source-root={source}", "--overwrite"]
    proc = subprocess.run(create, capture_output=True, text=True, env=env, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"CodeQL database failed for {task_id}/{revision}: {proc.stderr[-3000:]}")
    shape_queries, relation_queries = _queries(language)
    shapes, rows = [], {}
    try:
        for i, query in enumerate(shape_queries):
            shapes += verify.run_query(db, query, out_dir / f"shapes-{i}.json", env)
        shapes = sorted({tuple(row) for row in shapes})
        for name, query in relation_queries.items():
            rows[name] = verify.run_query(db, query, out_dir / f"relation-{name}.json", env)
        same_object = connector.query_rows(db, out_dir, language) if language == "go" else []
    except RuntimeError as e:
        raise RuntimeError(f"CodeQL query failed for {task_id}/{revision}: {e}") from None
    repo = GitRepo(t["repo"])
    query_files = [*shape_queries, *relation_queries.values()]
    if language == "go":
        query_files.append(connector.QUERY)
    doc = {
        "schema": "rd-analysis/v1", "status": "ok", "task_id": task_id,
        "fixture": t["fixture"], "revision": revision,
        "commit": t["revisions"][revision], "tree": repo.tree(t["revisions"][revision]),
        "language": language, "codeql": verify.reach.CODEQL_TAG,
        "queries": {str(p.relative_to(ROOT)): sha256(p) for p in sorted(set(query_files))},
        "shapes": [list(row) for row in shapes], "rows": rows,
        "same_object_rows": same_object,
    }
    data = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    frozen.write_bytes(gzip.compress(data, mtime=0))
    (out_dir / "provenance.json").write_text(json.dumps({
        "analysis_sha256_json": hashlib.sha256(data).hexdigest(),
        "analysis_sha256_gzip": sha256(frozen),
        "shape_rows": len(shapes), "relation_rows": {k: len(v) for k, v in rows.items()},
        "same_object_rows": len(same_object),
    }, indent=2) + "\n")
    shutil.rmtree(source, ignore_errors=True)
    # Phase B consumes only the compact, provenance-bound rows. Databases and decoded query
    # intermediates are reproducible build products and are not part of the freeze.
    shutil.rmtree(db, ignore_errors=True)
    for intermediate in out_dir.glob("*.bqrs"):
        intermediate.unlink()
    for intermediate in [*out_dir.glob("shapes-*.json"), *out_dir.glob("relation-*.json"),
                         out_dir / "same_object.json"]:
        if intermediate.exists():
            intermediate.unlink()
    print(f"{task_id}/{revision}: {len(shapes)} shapes, "
          f"{sum(map(len, rows.values()))} relation rows -> {frozen.relative_to(ROOT)}")
    return frozen


def build_one(task_id: str, revision: str, *, force: bool = False) -> Path:
    t = tasks.task(task_id)
    out_dir = RUNS / task_id / revision
    frozen = out_dir / "analysis.json.gz"
    if frozen.exists() and not force:
        doc = json.loads(gzip.decompress(frozen.read_bytes()))
        if doc.get("commit") == t["revisions"][revision] and doc.get("status") == "ok":
            return frozen
    if not force:
        # The one negative control is deliberately the same repository/revisions as its real task.
        # Reuse the deterministic query result while retaining a task-specific provenance envelope.
        for other_id in tasks.order():
            if other_id == task_id:
                continue
            other_task = tasks.task(other_id)
            other = RUNS / other_id / revision / "analysis.json.gz"
            if (other_task["fixture"], other_task["language"], other_task["revisions"][revision]) \
                    != (t["fixture"], t["language"], t["revisions"][revision]) or not other.exists():
                continue
            doc = json.loads(gzip.decompress(other.read_bytes()))
            if doc.get("status") != "ok" or doc.get("commit") != t["revisions"][revision]:
                continue
            out_dir.mkdir(parents=True, exist_ok=True)
            doc["task_id"] = task_id
            data = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
            frozen.write_bytes(gzip.compress(data, mtime=0))
            (out_dir / "provenance.json").write_text(json.dumps({
                "analysis_sha256_json": hashlib.sha256(data).hexdigest(),
                "analysis_sha256_gzip": sha256(frozen), "reused_from": other_id,
                "shape_rows": len(doc["shapes"]),
                "relation_rows": {k: len(v) for k, v in doc["rows"].items()},
                "same_object_rows": len(doc["same_object_rows"]),
            }, indent=2) + "\n")
            print(f"{task_id}/{revision}: reused deterministic analysis from {other_id}")
            return frozen
    return build_spec(t, task_id, revision, out_dir)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task", nargs="*", help="task ids (default: all in frozen order)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    selected = args.task or tasks.order()
    for task_id in selected:
        for revision in ("revision_A", "revision_B"):
            build_one(task_id, revision, force=args.force)


if __name__ == "__main__":
    main()
