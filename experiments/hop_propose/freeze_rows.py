"""Freeze the verifier output P-Hybrid-2 judges against (PREREGISTRATION.md §11.3).

    uv run python experiments/hop_propose/freeze_rows.py

Runs the frozen P-Hybrid-1 shape query and EVERY relation verifier of the fixture's
language (experiments/hop_verify/verify.py `analyze`, unchanged) on each revision of the
evaluation fixtures and the plumbing-pilot modules, and writes the rows, sorted, to
frozen/<fixture>.<revision>.json.gz plus a sha256 manifest. The runtime and the scorer
only ever read these files; no verifier runs during P-Hybrid-2.
"""

import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "hop_verify"))

import verify

OUT = HERE / "frozen"
SOURCES = {"eval": None, "dev": ["hopdev-go", "hopdev-py"]}


def main() -> None:
    relations = verify.relations()["relations"]
    manifest = {}
    for set_name, only in SOURCES.items():
        fixtures = verify.hop_set(set_name)["fixtures"]
        for fid, fixture in fixtures.items():
            if only and fid not in only:
                continue
            needed = {n for n, r in relations.items() if r["language"] == fixture["language"]}
            for rev in ("base", "head"):
                print(f"{fid} {rev}: {', '.join(sorted(needed))}", flush=True)
                work = ROOT / "runs" / "hop_propose" / "analysis" / fid / rev
                result = verify.analyze(fid, fixture, rev, needed, work)
                if result["status"] != "ok":
                    sys.exit(f"tool failure at {result['stage']}: {result['error'][:500]}")
                frozen = {"fixture": fid, "revision": rev, "commit": fixture["commits"][rev],
                          "language": fixture["language"],
                          "shapes": sorted(result["shapes"]),
                          "rows": {n: sorted(r) for n, r in sorted(result["rows"].items())}}
                data = json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()
                path = OUT / f"{fid}.{rev}.json.gz"
                path.write_bytes(gzip.compress(data, mtime=0))
                manifest[path.name] = {"sha256_json": hashlib.sha256(data).hexdigest(),
                                       "shapes": len(frozen["shapes"]),
                                       "rows": {n: len(r) for n, r in frozen["rows"].items()}}
    (OUT / "manifest.json").write_text(json.dumps(
        {"codeql": verify.reach.CODEQL_TAG, "files": manifest}, indent=2) + "\n")


if __name__ == "__main__":
    main()
