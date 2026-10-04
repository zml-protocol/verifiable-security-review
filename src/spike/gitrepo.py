"""Read-only access to a git repository through plumbing commands.

Everything is read from the object store by commit SHA, so no checkout is ever
touched and two revisions can be served side by side without materializing.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_HUNK_RE = re.compile(rb"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class GitError(RuntimeError):
    pass


@dataclass(frozen=True)
class GrepHit:
    path: str
    line: int
    text: str


@dataclass(frozen=True)
class FileChange:
    status: str  # A, M, D, R, C or T (git --raw status letter, similarity score dropped)
    old_path: str | None  # None when added
    new_path: str | None  # None when deleted


@dataclass(frozen=True)
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int


class GitRepo:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._trees: dict[str, tuple[str, ...]] = {}

    def _run(self, *args: str, ok_codes: tuple[int, ...] = (0,)) -> bytes:
        proc = subprocess.run(
            ["git", "-C", str(self.path), "-c", "core.quotePath=false", *args],
            capture_output=True,
            check=False,
        )
        if proc.returncode not in ok_codes:
            stderr = proc.stderr.decode(errors="replace").strip()
            raise GitError(f"git {args[0]} exited {proc.returncode}: {stderr}")
        return proc.stdout

    def resolve(self, ref: str) -> str:
        out = self._run("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")
        return out.decode().strip()

    def tree(self, commit: str) -> str:
        return self._run("rev-parse", f"{commit}^{{tree}}").decode().strip()

    def read_blob(self, commit: str, path: str) -> bytes | None:
        """Return the file's bytes at `commit`, or None if it does not exist there."""
        try:
            return self._run("cat-file", "blob", f"{commit}:{path}")
        except GitError:
            return None

    def ls_files(self, commit: str) -> tuple[str, ...]:
        if commit not in self._trees:
            out = self._run("ls-tree", "-r", "-z", "--name-only", commit)
            self._trees[commit] = tuple(p.decode(errors="replace") for p in out.split(b"\0") if p)
        return self._trees[commit]

    def grep(
        self,
        commit: str,
        pattern: str,
        pathspecs: list[str] | None = None,
        ignore_case: bool = False,
    ) -> list[GrepHit]:
        args = ["grep", "-n", "-I", "-z", "--no-color", "-E"]
        if ignore_case:
            args.append("-i")
        args += ["-e", pattern, commit, "--", *(pathspecs or [])]
        out = self._run(*args, ok_codes=(0, 1))
        prefix = f"{commit}:".encode()
        hits = []
        for record in out.split(b"\n"):
            if not record:
                continue
            name, lineno, text = record.split(b"\0", 2)
            hits.append(
                GrepHit(
                    path=name.removeprefix(prefix).decode(errors="replace"),
                    line=int(lineno),
                    text=text.decode(errors="replace"),
                )
            )
        return hits

    def changed_files(self, old: str, new: str) -> list[FileChange]:
        out = self._run("diff", "--raw", "-z", "-M", "--no-abbrev", old, new)
        fields = out.split(b"\0")
        changes = []
        i = 0
        while i < len(fields) and fields[i]:
            status = fields[i].split()[-1].decode()[0]
            if status in "RC":
                old_path, new_path = fields[i + 1].decode(), fields[i + 2].decode()
                i += 3
            else:
                path = fields[i + 1].decode()
                old_path = None if status == "A" else path
                new_path = None if status == "D" else path
                i += 2
            changes.append(FileChange(status, old_path, new_path))
        return changes

    def diff(self, old: str, new: str, paths: list[str], context: int = 3) -> bytes:
        return self._run(
            "diff", f"-U{context}", "-M", "--no-color", "--no-ext-diff", old, new, "--", *paths
        )

    def hunks(self, old: str, new: str, paths: list[str]) -> list[Hunk]:
        """Zero-context hunks, i.e. exactly the changed line ranges on each side."""
        result = []
        for line in self.diff(old, new, paths, context=0).splitlines():
            m = _HUNK_RE.match(line)
            if m:
                a, b, c, d = m.groups()
                result.append(
                    Hunk(int(a), 1 if b is None else int(b), int(c), 1 if d is None else int(d))
                )
        return result
