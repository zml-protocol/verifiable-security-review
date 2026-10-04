"""Build the Spike P Python calibration module (not an evaluation fixture).

    python fixtures/_pilot/build_pyregistry.py   # -> .cache/fixtures/pilot-pyregistry, tag `base`

Three relation shapes with no code shared with any evaluation fixture:
a plain call (plumbing sanity), a call on an attribute typed in __init__
(call_typed_attribute), and a method chosen from a registry by a key taken
from the input (registry_dispatch).
"""

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / ".cache" / "fixtures" / "pilot-pyregistry"

REGISTRY_PY = '''"""Spike P calibration module (not an evaluation fixture)."""
class Checker:
    name = "base"

    def check(self, label, proof):
        return False


class Relaxed(Checker):
    name = "relaxed"

    def check(self, label, proof):
        return proof == ""


class Exact(Checker):
    name = "exact"

    def check(self, label, proof):
        return False


TABLE = {cls.name: cls() for cls in (Relaxed, Exact)}


class Engine:
    def run(self, ticket):
        label, proof = ticket.split(".")
        chosen = TABLE[label]
        return chosen.check(label, proof)


class Front:
    def __init__(self):
        self._engine = Engine()

    def submit(self, ticket):
        return self._engine.run(ticket)


def outer(value):
    return inner(value)


def inner(item):
    return item.strip()
'''


def main() -> None:
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    (DEST / "registry.py").write_text(REGISTRY_PY)
    env = {**os.environ, "GIT_AUTHOR_NAME": "pilot", "GIT_AUTHOR_EMAIL": "pilot@example.invalid",
           "GIT_COMMITTER_NAME": "pilot", "GIT_COMMITTER_EMAIL": "pilot@example.invalid",
           "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}
    for cmd in (["init", "-q", "-b", "main"], ["add", "-A"],
                ["commit", "-q", "--no-gpg-sign", "-m", "pilot"], ["tag", "base"]):
        subprocess.run(["git", "-C", str(DEST), *cmd], env=env, check=True)
    print(subprocess.run(["git", "-C", str(DEST), "rev-parse", "base"],
                         capture_output=True, text=True, check=True).stdout.strip())


if __name__ == "__main__":
    main()
