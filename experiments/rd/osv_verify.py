"""Verify a copy of the frozen RD OSV snapshot against its manifest (PREREGISTRATION.md §15.2).

    uv run python experiments/rd/osv_verify.py [DIR]   # default: the manifest's local_dir

Checks each zip's byte size and SHA-256 and that it is a valid archive. The candidate pool is
built only from a copy that passes. Exit status 1 on any mismatch or missing file.
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "experiments" / "rd" / "osv-snapshot.json"


def problems(directory: Path) -> list[str]:
    manifest = json.loads(MANIFEST.read_text())
    out = []
    for eco, entry in manifest["files"].items():
        path = directory / entry["file"]
        if not path.exists():
            out.append(f"{eco}: {path} missing")
            continue
        data = path.read_bytes()
        if len(data) != entry["bytes"]:
            out.append(f"{eco}: {len(data)} bytes, manifest {entry['bytes']}")
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            out.append(f"{eco}: sha256 differs from the manifest")
        elif zipfile.ZipFile(path).testzip() is not None:
            out.append(f"{eco}: corrupt archive")
    return out


def main() -> None:
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / json.loads(MANIFEST.read_text())["local_dir"]
    found = problems(directory)
    for p in found:
        print(p)
    print(f"{directory}: {'OK' if not found else f'{len(found)} problems'}")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
