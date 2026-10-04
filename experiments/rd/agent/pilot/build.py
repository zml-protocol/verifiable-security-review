"""Build the deterministic two-commit synthetic RD plumbing repository."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REPO = ROOT / ".cache" / "rd" / "agent-pilot"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "RD Pilot", "GIT_AUTHOR_EMAIL": "rd@example.invalid",
       "GIT_COMMITTER_NAME": "RD Pilot", "GIT_COMMITTER_EMAIL": "rd@example.invalid",
       "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], env=ENV, capture_output=True,
                          text=True, check=True).stdout.strip()


def copy_source(name: str) -> None:
    source = HERE / name
    for old in REPO.iterdir():
        if old.name != ".git":
            if old.is_dir():
                shutil.rmtree(old)
            else:
                old.unlink()
    for item in source.iterdir():
        shutil.copyfile(item, REPO / item.name)


def build() -> dict:
    if REPO.exists():
        shutil.rmtree(REPO)
    REPO.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(REPO)], check=True)
    copy_source("source-a")
    git("add", ".")
    git("commit", "-qm", "synthetic revision A")
    a = git("rev-parse", "HEAD")
    copy_source("source-b")
    git("add", ".")
    git("commit", "-qm", "synthetic revision B")
    b = git("rev-parse", "HEAD")
    return {"repo": str(REPO), "revision_A": a, "revision_B": b,
            "tree_A": git("rev-parse", f"{a}^{{tree}}"), "tree_B": git("rev-parse", f"{b}^{{tree}}")}


if __name__ == "__main__":
    print(build())
