"""Build and score the public provider development corpus without any model call."""

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
PARENT = HERE.parent
ROOT = HERE.parents[3]
for directory in (HERE, PARENT):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import graph  # noqa: E402
import rdv3_analysis as analysis  # noqa: E402

CORPUS = HERE / "provider-development-v2.yaml"
OUT = ROOT / "runs" / "rd" / "agent" / "rd-v3" / "development" / "provider"
RESULT = OUT / "result.json"


class ProviderDevError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str, env: dict | None = None) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                            env=env, check=False)
    if result.returncode:
        raise ProviderDevError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def materialize(case: dict, *, force: bool, out: Path = OUT) -> tuple[Path, str, str]:
    root = out / case["target"]
    repo = root / "repo"
    source_hash = sha256_bytes(json.dumps(case["files"], sort_keys=True).encode())
    provenance = root / "source.json"
    if repo.exists() and provenance.exists() and not force:
        doc = json.loads(provenance.read_text())
        if doc.get("source_sha256") == source_hash:
            return repo, doc["commit"], source_hash
        raise ProviderDevError(f"development source drift for {case['target']}; rerun with --force")
    if root.exists():
        if not force:
            raise ProviderDevError(f"partial development output exists: {root}")
        shutil.rmtree(root)
    repo.mkdir(parents=True)
    for name, source in case["files"].items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    if case["language"] == "go":
        (repo / "go.mod").write_text(f"module example.invalid/{case['target']}\n\ngo 1.26\n")
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "RD V3 Provider Development")
    git(repo, "config", "user.email", "rd-v3-provider@example.invalid")
    git(repo, "add", ".")
    env = {**os.environ, "GIT_AUTHOR_DATE": "2026-10-03T00:00:00Z",
           "GIT_COMMITTER_DATE": "2026-10-03T00:00:00Z"}
    git(repo, "commit", "-qm", "synthetic provider development", env=env)
    commit = git(repo, "rev-parse", "HEAD")
    provenance.write_text(json.dumps({"target": case["target"], "source_sha256": source_hash,
                                      "commit": commit}, indent=2) + "\n")
    return repo, commit, source_hash


def one(case: dict, *, force: bool, out: Path = OUT) -> dict:
    repo, commit, source_hash = materialize(case, force=force, out=out)
    task = {"fixture": f"synthetic/{case['target']}", "language": case["language"],
            "repo": str(repo), "revisions": {"revision_A": commit, "revision_B": commit}}
    analysis_path = analysis.build_spec(
        task, case["target"], "revision_A", out / case["target"] / "analysis")
    document = json.loads(gzip.decompress(analysis_path.read_bytes()))
    scorer = graph.GraphScorer(language=case["language"], repo=str(repo),
                               revisions=task["revisions"], analysis={"revision_A": document})
    rows = []
    for edge in case["edges"]:
        hop = {"revision": "revision_A", "relation": case["relation"],
               "from": edge["from"], "to": edge["to"]}
        state, _ = scorer.resolve_hop(hop)
        rows.append({"id": edge["id"], "truth": edge["truth"],
                     "false_family": edge.get("false_family"), "state": state})
    unsafe = [row for row in rows if row["truth"] is False and row["state"] == "VERIFIED"]
    true_rows = [row for row in rows if row["truth"] is True]
    verified_true = sum(row["state"] == "VERIFIED" for row in true_rows)
    if unsafe:
        disposition = "UNSAFE_PROVIDER"
    elif verified_true == len(true_rows):
        disposition = "SUPPORTED"
    elif verified_true:
        disposition = "PARTIAL"
    else:
        disposition = "UNSUPPORTED"
    return {"target": case["target"], "language": case["language"],
            "relation": case["relation"], "source_sha256": source_hash,
            "analysis_sha256": hashlib.sha256(analysis_path.read_bytes()).hexdigest(),
            "disposition": disposition, "edges": rows}


def run(*, force: bool = False) -> dict:
    doc = yaml.safe_load(CORPUS.read_text())
    if doc.get("schema") != "rd-v3-provider-development/v2":
        raise ProviderDevError("provider development corpus is not v2")
    results = [one(case, force=force) for case in doc["cases"]]
    result = {"schema": "rd-v3-provider-development-result/v1",
              "corpus_sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
              "targets": results,
              "unsafe": any(row["disposition"] == "UNSAFE_PROVIDER" for row in results)}
    OUT.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    return result


def run_target(target: str, *, force: bool = False) -> dict:
    """Run one public development target without replacing the full-corpus result."""
    doc = yaml.safe_load(CORPUS.read_text())
    if doc.get("schema") != "rd-v3-provider-development/v2":
        raise ProviderDevError("provider development corpus is not v2")
    matches = [case for case in doc["cases"] if case["target"] == target]
    if len(matches) != 1:
        raise ProviderDevError(f"unknown or duplicate development target: {target}")
    return one(matches[0], force=force)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--target", help="run one public development target only")
    args = parser.parse_args()
    result = run_target(args.target, force=args.force) if args.target else run(force=args.force)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
